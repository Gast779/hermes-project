"""
LP Yield Scanner — аналіз yield farming + impermanent loss.

Функціонал (read-only):
    - Uniswap v2/v3 TVL + APR
    - Aave/Pendle yield stats
    - Impermanent loss estimation
    - Yield aggregator comparison

Usage:
    from lp_yield import LPScanner
    scanner = LPScanner()
    pools = scanner.find_best_pools(chain="ethereum", min_tvl_usd=1_000_000)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
@dataclass
class LPPool:
    """Пул ліквідності з метриками."""
    name: str                # напр. "ETH-USDC 0.3%"
    protocol: str            # "uniswap_v3", "curve", "aave"
    chain: str
    tvl_usd: float
    apy: float               # річна дохідність (%)
    volume_24h: float
    fees_24h: float
    impermanent_loss_1m: float | None  # історичне IL 1 місяць
    token0: str
    token1: str
    risk_score: float        # 0..1 (higher = riskier)
    url: str | None


# --------------------------------------------------------------------------- #
class LPScanner:
    """Сканер yield farming пулів з оцінкою ризику."""

    def __init__(self):
        self._http = httpx.Client(timeout=15.0)

    # ---- DefiLlama APIs (public, no key) ------------------------------------ #
    def _defillama(self, endpoint: str) -> Any:
        """DefiLlama API."""
        url = f"https://yields.llama.fi/{endpoint}"
        try:
            r = self._http.get(url)
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    def get_pools(self, chain: str | None = None, min_tvl: float = 0) -> list[LPPool]:
        """Отримати всі пули з DefiLlama."""
        try:
            data = self._defillama("pools")
        except Exception:
            log.warning("DefiLlama API unavailable, using stubs")
            return self._stub_pools()
        pools = []
        for p in data.get("data", []):
            tvl = p.get("tvlUsd", 0)
            if tvl < min_tvl:
                continue
            if chain and p.get("chain", "").lower() != chain.lower():
                continue
            
            # Risk heuristics
            apy = (p.get("apy") or 0) or (p.get("apyBase") or 0)
            risk = self._calculate_risk(p, apy, tvl)
            tokens = p.get("underlyingTokens") or ["?", "?"]
            
            pools.append(LPPool(
                name=p.get("symbol", "?"),
                protocol=p.get("project", "?"),
                chain=p.get("chain", "?"),
                tvl_usd=tvl,
                apy=apy,
                volume_24h=p.get("volumeUsd1d", 0),
                fees_24h=p.get("feesUsd1d", 0),
                impermanent_loss_1m=p.get("il7d", 0) * 4 if p.get("il7d") is not None else None,
                token0=tokens[0] if len(tokens) > 0 else "?",
                token1=tokens[1] if len(tokens) > 1 else "?",
                risk_score=risk,
                url=p.get("url"),
            ))
        pools.sort(key=lambda p: p.apy * (1 - p.risk_score), reverse=True)
        return pools

    def find_best_pools(
        self,
        chain: str | None = None,
        min_tvl_usd: float = 1_000_000,
        max_risk: float = 0.7,
        top_n: int = 10,
    ) -> list[LPPool]:
        """Знайти найкращі пули за risk-adjusted returns."""
        pools = self.get_pools(chain=chain, min_tvl=min_tvl_usd)
        filtered = [p for p in pools if p.risk_score <= max_risk]
        return filtered[:top_n]

    def _calculate_risk(self, raw: dict, apy: float, tvl: float) -> float:
        """Оцінка ризику пулу (0..1)."""
        risk = 0.0
        # High APY = higher risk
        if apy > 50:
            risk += 0.3
        elif apy > 20:
            risk += 0.15
        # Low TVL = higher risk
        if tvl < 10_000_000:
            risk += 0.2
        elif tvl < 50_000_000:
            risk += 0.1
        # New/untested protocols
        if (raw.get("apyReward") or 0) > 0:
            risk += 0.1  # reward tokens add risk
        return min(risk, 1.0)

    def _stub_pools(self) -> list[LPPool]:
        """Тестові дані пулів."""
        return [
            LPPool(
                name="ETH-USDC 0.05%",
                protocol="uniswap_v3",
                chain="ethereum",
                tvl_usd=500_000_000,
                apy=8.5,
                volume_24h=150_000_000,
                fees_24h=75_000,
                impermanent_loss_1m=0.02,
                token0="ETH",
                token1="USDC",
                risk_score=0.15,
                url="https://app.uniswap.org",
            ),
            LPPool(
                name="WBTC-ETH 0.3%",
                protocol="uniswap_v3",
                chain="ethereum",
                tvl_usd=200_000_000,
                apy=5.2,
                volume_24h=40_000_000,
                fees_24h=120_000,
                impermanent_loss_1m=0.01,
                token0="WBTC",
                token1="ETH",
                risk_score=0.1,
                url="https://app.uniswap.org",
            ),
            LPPool(
                name="USDC-USDT 0.01%",
                protocol="curve",
                chain="ethereum",
                tvl_usd=800_000_000,
                apy=12.5,
                volume_24h=200_000_000,
                fees_24h=200_000,
                impermanent_loss_1m=0.001,
                token0="USDC",
                token1="USDT",
                risk_score=0.05,
                url="https://curve.fi",
            ),
        ]

    # ---- Publish ---------------------------------------------------------- #
    def publish_pool(self, pool: LPPool) -> None:
        """Опублікувати LP пул в event bus."""
        try:
            from coordination.event_bus import get_bus, SignalEvent
            bus = get_bus()
            bus.publish(SignalEvent(
                source="lp_yield_scanner",
                topic="lp.opportunity",
                payload={
                    "name": pool.name,
                    "protocol": pool.protocol,
                    "chain": pool.chain,
                    "tvl_usd": pool.tvl_usd,
                    "apy": pool.apy,
                    "risk_score": pool.risk_score,
                    "impermanent_loss_1m": pool.impermanent_loss_1m,
                },
                priority=0,
            ))
        except Exception:
            log.exception("Event bus publish failed")

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def get_lp_scanner() -> DefiLlamLPScanner:
    """Singleton accessor."""
    return DefiLlamLPScanner()
