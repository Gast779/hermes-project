"""
Deribit Derivatives Analyzer — basis trade + funding rate stub.

Функціонал:
    - Fetch BTC/ETH perpetual perpetual price
    - Fetch Futures (monthly/quarterly) prices
    - Calculate basis = futures_price - spot_price
    - Calculate funding rate & annualized yield
    - Identify basis arbitrage opportunities
    
Read-only: не торгує, тільки аналізує.

Usage:
    from deribit import DeribitAnalyzer
    analyzer = DeribitAnalyzer()
    opps = analyzer.find_basis_arbitrage()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
@dataclass
class BasisOpportunity:
    """Можливість basis arbitrage."""
    symbol: str              # BTC-PERPETUAL, ETH-PERPETUAL
    futures_price: float
    spot_price: float
    basis: float             # futures - spot
    basis_percent: float     # basis / spot * 100
    funding_rate_1h: float | None
    funding_rate_ann: float | None  # annualized
    days_to_expiry: int | None
    signal: str              # "contango" (basis > 0) | "backwardation"
    confidence: float        # 0..1


# --------------------------------------------------------------------------- #
class DeribitAnalyzer:
    """Аналіз ринків Deribit: basis, funding, арбітраж."""

    BASE_URL = "https://test.deribit.com/api/v2"  # testnet initially

    def __init__(self, api_key: str | None = None, api_secret: str | None = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self._http = httpx.Client(timeout=15.0)

    # ---- API helpers ----------------------------------------------------- #
    def _request(self, method: str, params: dict | None = None) -> Any:
        """JSON-RPC запит до Deribit API."""
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": method,
            "params": params or {},
        }
        r = self._http.post(self.BASE_URL + "/public/" + method, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"Deribit API error: {data['error']}")
        return data.get("result", {})

    # ---- Perpetual + Spot data -------------------------------------------- #
    def get_perpetual(self, currency: str = "BTC", kind: str = "future") -> dict:
        """Отримати дані perpetual futures."""
        return self._request("get_book_summary_by_currency", {
            "currency": currency,
            "kind": kind,
        })

    def get_futures_summary(self, currency: str = "BTC") -> list[dict]:
        """Список всіх futures."""
        return self._request("get_instruments", {
            "currency": currency,
            "kind": "future",
            "expired": False,
        })

    def get_funding_rate(self, instrument: str) -> dict:
        """Funding rate для perpetual."""
        return self._request("get_funding_rate_value", {
            "instrument_name": instrument,
            "start_timestamp": int((time.time() - 86400) * 1000),
            "end_timestamp": int(time.time() * 1000),
        })

    def get_ticker(self, instrument: str) -> dict:
        """Поточна ціна інструменту."""
        return self._request("ticker", {"instrument_name": instrument})

    # ---- Analysis --------------------------------------------------------- #
    def find_basis_arbitrage(
        self,
        currency: str = "BTC",
        min_basis_bps: float = 50.0,  # min 50 basis points
    ) -> list[BasisOpportunity]:
        """
        Знайти basis arbitrage: perpetual vs futures.
        
        Contango: futures > spot → short futures, long spot (or hold)
        Backwardation: futures < spot → long futures, short spot
        
        Returns basis opportunities with funding rate info.
        """
        log.info("Scanning Deribit %s basis arb (min %s bps)", currency, min_basis_bps)
        
        # Get all instruments
        try:
            instruments = self.get_futures_summary(currency)
        except Exception as e:
            log.warning("Deribit API unavailable (stub mode): %s", e)
            # Return stub data for testing
            return self._stub_basis_opportunities(currency)

        # Find perpetual
        perp_name = None
        for inst in instruments:
            if "PERPETUAL" in inst.get("instrument_name", ""):
                perp_name = inst["instrument_name"]
                break
        
        if not perp_name:
            log.warning("No perpetual found for %s", currency)
            return []

        try:
            perp_ticker = self.get_ticker(perp_name)
            perp_price = perp_ticker.get("mark_price", perp_ticker.get("last_price", 0))
        except Exception:
            perp_price = 0
            log.warning("Failed to get %s price", perp_name)

        opps: list[BasisOpportunity] = []
        for inst in instruments:
            name = inst.get("instrument_name", "")
            if "PERPETUAL" in name:
                continue  # skip perpetual itself
            
            try:
                ticker = self.get_ticker(name)
                fut_price = ticker.get("mark_price", ticker.get("last_price", 0))
                
                # Days to expiry
                exp_ts = inst.get("expiration_timestamp")
                days = int((exp_ts - time.time()*1000) / 86400000) if exp_ts else None
                
                basis = fut_price - perp_price
                basis_pct = basis / perp_price * 100 if perp_price else 0
                
                # Check funding
                try:
                    funding = self.get_funding_rate(perp_name)
                    funding_1h = funding.get("interest_1h", 0)
                    funding_ann = funding_1h * 24 * 365 if funding_1h else None
                except Exception:
                    funding_1h = None
                    funding_ann = None

                if abs(basis_pct*100) >= min_basis_bps:  # min_basis_bps is in basis points
                    opps.append(BasisOpportunity(
                        symbol=name,
                        futures_price=fut_price,
                        spot_price=perp_price,
                        basis=basis,
                        basis_percent=basis_pct,
                        funding_rate_1h=funding_1h,
                        funding_rate_ann=funding_ann,
                        days_to_expiry=days,
                        signal="contango" if basis > 0 else "backwardation",
                        confidence=min(abs(basis_pct) / 2, 1.0),  # ~2% = 100% confidence
                    ))
            except Exception as e:
                log.debug("Failed analyzing %s: %s", name, e)
                continue

        opps.sort(key=lambda o: abs(o.basis_percent), reverse=True)
        return opps

    def _stub_basis_opportunities(self, currency: str) -> list[BasisOpportunity]:
        """Тестові дані якщо API недоступний."""
        price = 95000.0 if currency == "BTC" else 3500.0
        return [
            BasisOpportunity(
                symbol=f"{currency}-25MAR25",
                futures_price=price * 1.005,
                spot_price=price,
                basis=price * 0.005,
                basis_percent=0.5,
                funding_rate_1h=0.0001,
                funding_rate_ann=0.876,
                days_to_expiry=90,
                signal="contango",
                confidence=0.7,
            ),
            BasisOpportunity(
                symbol=f"{currency}-27JUN25",
                futures_price=price * 1.012,
                spot_price=price,
                basis=price * 0.012,
                basis_percent=1.2,
                funding_rate_1h=0.0001,
                funding_rate_ann=0.876,
                days_to_expiry=180,
                signal="contango",
                confidence=0.85,
            ),
        ]

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def get_deribit_analyzer() -> DeribitAnalyzer:
    """Повернути shared instance DeribitAnalyzer."""
    return DeribitAnalyzer()
