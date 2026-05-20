"""
Crypto Monitor
==============

Два потоки:
1. **Звіти** — 3 рази на день (09:00 / 15:00 / 21:00 за Europe/Kyiv).
   Стан ринку, топ-10, гейнери/лозери, новини.
2. **Алерти** — фоновий моніторинг fast-movers:
       *  > 5% за 5 хвилин
       *  > 20% за 1 годину

Дані: CoinGecko (основне) + Binance ticker (опційно для крос-перевірки).
"""

from .data_sources import CoinGeckoClient, BinanceClient
from .reports import generate_daily_report
from .alerts import FastMoversWatcher
from .scheduler import build_scheduler

__all__ = [
    "CoinGeckoClient",
    "BinanceClient",
    "generate_daily_report",
    "FastMoversWatcher",
    "build_scheduler",
]
