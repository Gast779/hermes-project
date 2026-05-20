"""
Клієнти до CoinGecko (основне джерело) і Binance (доп. для тикерів).

CoinGecko Demo plan:
    base = https://api.coingecko.com/api/v3
    header = x-cg-demo-api-key: <KEY>
    limit  = 30 req/min

Якщо у тебе Pro/Analyst plan — змінюй base на https://pro-api.coingecko.com/api/v3
і header на x-cg-pro-api-key.

Binance публічні endpoints не вимагають ключа.
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
class CoinTicker:
    id: str
    symbol: str
    name: str
    price_usd: float
    market_cap_usd: float
    total_volume_usd: float
    pct_change_1h: float | None
    pct_change_24h: float | None
    pct_change_7d: float | None


# --------------------------------------------------------------------------- #
class CoinGeckoClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.coingecko.com/api/v3",
        timeout: float = 15.0,
        min_request_interval: float = 2.5,    # ~24 req/min — нижче за ліміт 30
    ):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.min_request_interval = min_request_interval
        self._last_call = 0.0
        headers = {"Accept": "application/json"}
        if api_key:
            # Demo чи Pro — заголовок підбирається автоматично
            if "pro-api" in base_url:
                headers["x-cg-pro-api-key"] = api_key
            else:
                headers["x-cg-demo-api-key"] = api_key
        self._http = httpx.Client(timeout=timeout, headers=headers)

    def _throttle(self) -> None:
        delta = time.monotonic() - self._last_call
        if delta < self.min_request_interval:
            time.sleep(self.min_request_interval - delta)
        self._last_call = time.monotonic()

    def _get(self, path: str, params: dict | None = None) -> Any:
        self._throttle()
        for attempt in range(1, 4):
            try:
                r = self._http.get(f"{self.base}{path}", params=params)
                if r.status_code == 429:
                    wait = 5 * attempt
                    log.warning("CoinGecko 429; sleeping %ss", wait)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                if attempt == 3:
                    raise
                log.warning("CoinGecko error %s (attempt %s)", e, attempt)
                time.sleep(2 ** attempt)

    # ---- public methods --------------------------------------------------- #
    def get_global(self) -> dict:
        """Загальний стан ринку: total cap, BTC dominance, total volume."""
        return self._get("/global").get("data", {})

    def get_top_markets(
        self,
        *,
        vs: str = "usd",
        per_page: int = 50,
        page: int = 1,
        price_change: str = "1h,24h,7d",
    ) -> list[CoinTicker]:
        """Топ N монет за капіталізацією зі змінами за різні таймфрейми."""
        data = self._get(
            "/coins/markets",
            params={
                "vs_currency": vs,
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
                "price_change_percentage": price_change,
            },
        )
        return [self._parse(c) for c in data]

    def get_movers(
        self,
        *,
        per_page: int = 250,
        pages: int = 2,
    ) -> tuple[list[CoinTicker], list[CoinTicker]]:
        """
        Стягуємо топ-(pages × per_page) і повертаємо (top_gainers_24h, top_losers_24h).
        Free CoinGecko не має «trending movers» endpoint, тому робимо локально.
        """
        all_: list[CoinTicker] = []
        for p in range(1, pages + 1):
            all_.extend(self.get_top_markets(per_page=per_page, page=p, price_change="24h"))
        valid = [c for c in all_ if c.pct_change_24h is not None]
        gainers = sorted(valid, key=lambda c: c.pct_change_24h, reverse=True)[:10]
        losers  = sorted(valid, key=lambda c: c.pct_change_24h)[:10]
        return gainers, losers

    def get_trending(self) -> list[dict]:
        """Trending за останні 24h (за пошуками на CoinGecko)."""
        return self._get("/search/trending").get("coins", [])

    @staticmethod
    def _parse(c: dict) -> CoinTicker:
        return CoinTicker(
            id=c["id"],
            symbol=c.get("symbol", "").upper(),
            name=c.get("name", ""),
            price_usd=float(c.get("current_price") or 0),
            market_cap_usd=float(c.get("market_cap") or 0),
            total_volume_usd=float(c.get("total_volume") or 0),
            pct_change_1h=c.get("price_change_percentage_1h_in_currency"),
            pct_change_24h=c.get("price_change_percentage_24h_in_currency")
                          or c.get("price_change_percentage_24h"),
            pct_change_7d=c.get("price_change_percentage_7d_in_currency"),
        )

    def close(self) -> None:
        self._http.close()


# --------------------------------------------------------------------------- #
class BinanceClient:
    """Public ticker — для крос-перевірки CoinGecko (без ключа)."""

    def __init__(self, base_url: str = "https://api.binance.com", timeout: float = 10.0):
        self.base = base_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout, headers={"Accept": "application/json"})

    def get_24h_tickers(self) -> list[dict]:
        r = self._http.get(f"{self.base}/api/v3/ticker/24hr")
        r.raise_for_status()
        return r.json()

    def get_klines(self, symbol: str, interval: str = "5m", limit: int = 12) -> list[list]:
        """
        OHLCV-свічки. interval: 1m,5m,15m,1h,...
        Повертає [[open_time, open, high, low, close, volume, close_time, ...], ...]
        """
        r = self._http.get(
            f"{self.base}/api/v3/klines",
            params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
        )
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()
