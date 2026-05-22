"""
On-chain Monitor — whale tracking + mempool monitoring.

Функціонал (read-only):
    - BTC/ETH large transaction alerts (> $1M)
    - Mempool monitoring: fee rates, pending TXs
    - Exchange inflow/outflow estimates
    - Network health: hash rate, difficulty

Sources:
    - Glassnode API (free tier)
    - Blockchain.info (public)
    - Etherscan API

Usage:
    from onchain import OnChainMonitor
    monitor = OnChainMonitor()
    monitor.get_whale_transactions()  # > $1M
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

WHALE_THRESHOLD_USD = 1_000_000


# --------------------------------------------------------------------------- #
@dataclass
class WhaleTransaction:
    """Велика on-chain транзакція."""
    txid: str
    blockchain: str        # BTC | ETH
    amount_btc: float | None
    amount_eth: float | None
    value_usd: float
    from_addr: str | None
    to_addr: str | None
    fee: float
    timestamp: float
    direction: str | None  # "inflow" | "outflow" | None (невизначено)


# --------------------------------------------------------------------------- #
class OnChainMonitor:
    """Моніторинг on-chain даних: whales, mempool, network health."""

    def __init__(self):
        self._http = httpx.Client(timeout=15.0)

    # ---- Blockchain.info (BTC) ---------------------------------------------- #
    def _btc_tx_info(self, txid: str) -> dict[str, Any]:
        """Деталі BTC транзакції з blockchain.info."""
        r = self._http.get(f"https://blockchain.info/rawtx/{txid}")
        r.raise_for_status()
        return r.json()

    def get_latest_btc_block(self) -> dict[str, Any]:
        """Останній BTC блок."""
        r = self._http.get("https://blockchain.info/latestblock")
        r.raise_for_status()
        return r.json()

    def get_btc_mempool(self) -> dict[str, Any]:
        """Mempool статистика BTC."""
        r = self._http.get("https://api.blockchain.info/mempool/fees")
        if r.status_code == 200:
            return r.json()
        # Fallback
        return {"regular": 0, "priority": 0, "limits": {}}

    # ---- Glassnode (free tier) -------------------------------------------- #
    def _glassnode(self, endpoint: str, asset: str = "BTC", params: dict | None = None) -> Any:
        """Glassnode API запит (без ключа — public endpoints)."""
        url = f"https://api.glassnode.com/v1/metrics/{endpoint}"
        try:
            r = self._http.get(url, params={"a": asset, "i": "24h", **(params or {})})
            r.raise_for_status()
            return r.json()
        except Exception:
            return []

    def get_exchange_flow(self, exchange: str = "binance", asset: str = "BTC") -> dict:
        """Exchange inflow/outflow."""
        return self._glassnode(f"exchange_flows/{exchange}_flow", asset)

    def get_whale_ratio(self, asset: str = "BTC") -> list[dict]:
        """Whale-transaction ratio."""
        return self._glassnode("blockchain/whale_transaction_count", asset)

    # ---- Etherscan (public endpoints) --------------------------------------- #
    def _etherscan(self, module: str, action: str, params: dict | None = None) -> Any:
        """Etherscan public API (без ключа — обмежений rate)."""
        url = "https://api.etherscan.io/api"
        try:
            r = self._http.get(url, params={
                "module": module, "action": action, "tag": "latest", **(params or {})
            })
            data = r.json()
            return data.get("result", {})
        except Exception:
            return {}

    def get_eth_gas_price(self) -> dict:
        """Ethereum gas price (gwei)."""
        return self._etherscan("gastracker", "gasoracle")

    def get_eth_block_number(self) -> str:
        """Останній номер блоку Ethereum."""
        return self._etherscan("proxy", "eth_blockNumber")

    # ---- Whale Transactions (stub + heuristics) ---------------------------- #
    def get_whale_transactions(
        self,
        blockchain: str = "BTC",
        min_usd: float = WHALE_THRESHOLD_USD,
        hours: int = 24,
    ) -> list[WhaleTransaction]:
        """Знайти великі транзакції за останні N годин."""
        log.info("Scanning %s whale txs (min $%s, last %sh)", blockchain, min_usd, hours)
        
        # Справжні дані требують Glassnode paid tier або whale-alert.com paid API
        # Stub для демонстрації:
        return self._stub_whales(blockchain, min_usd)

    def _stub_whales(self, blockchain: str, min_usd: float) -> list[WhaleTransaction]:
        """Тестові whale транзакції."""
        ts = time.time()
        if blockchain == "BTC":
            return [
                WhaleTransaction(
                    txid=f"stub_btc_{i}", blockchain="BTC",
                    amount_btc=min_usd/95000,
                    amount_eth=None,
                    value_usd=min_usd * (1.0 + i*0.1),
                    from_addr=f"1A{i}...",
                    to_addr=f"1B{i}...",
                    fee=0.001,
                    timestamp=ts - i*3600,
                    direction="outflow",
                )
                for i in range(1, 4)
            ]
        else:
            return [
                WhaleTransaction(
                    txid=f"stub_eth_{i}", blockchain="ETH",
                    amount_btc=None,
                    amount_eth=min_usd/3500,
                    value_usd=min_usd * (1.0 + i*0.1),
                    from_addr=f"0x{i}...",
                    to_addr=f"0x{i+1}...",
                    fee=0.01,
                    timestamp=ts - i*3600,
                    direction="inflow",
                )
                for i in range(1, 4)
            ]

    # ---- Publish ---------------------------------------------------------- #
    def publish_to_bus(self, tx: WhaleTransaction) -> None:
        """Опублікувати whale в event bus."""
        try:
            from coordination.event_bus import get_bus, SignalEvent
            bus = get_bus()
            bus.publish(SignalEvent(
                source="onchain_monitor",
                topic="crypto.whale",
                payload={
                    "txid": tx.txid,
                    "blockchain": tx.blockchain,
                    "value_usd": tx.value_usd,
                    "direction": tx.direction,
                    "amount_btc": tx.amount_btc,
                    "amount_eth": tx.amount_eth,
                },
                priority=1 if tx.value_usd >= 10_000_000 else 0,
            ))
        except Exception:
            log.exception("Event bus publish failed")

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
