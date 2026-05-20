"""
Polymarket Analyzer
===================

Модуль для аналізу prediction-ринків Polymarket.

API, які використовуємо:
    - Gamma API  (gamma-api.polymarket.com) — метадані ринків, події, slug, теги.
    - CLOB API   (clob.polymarket.com)      — реальний orderbook (bid/ask) по токенах.
    - CLOB WS    (ws-subscriptions-clob...) — стрім оновлень orderbook у реальному часі.

Архітектура:
    client.py             — HTTP-клієнт до Gamma + CLOB
    arbitrage_internal.py — пошук арбітражу всередині Polymarket
    cross_market.py       — порівняння Polymarket з іншими prediction-маркетами
    topic_monitor.py      — моніторинг ринків за обраною темою
    realtime.py           — WebSocket-підписка на зміни orderbook
    reporter.py           — форматування звітів у markdown
"""

from .client import PolymarketClient
from .arbitrage_internal import InternalArbitrageFinder, ArbitrageOpportunity
from .topic_monitor import TopicMonitor
from .cross_market import CrossMarketAnalyzer, ExternalMarket
from .reporter import format_arbitrage_report, format_topic_report

__all__ = [
    "PolymarketClient",
    "InternalArbitrageFinder",
    "ArbitrageOpportunity",
    "TopicMonitor",
    "CrossMarketAnalyzer",
    "ExternalMarket",
    "format_arbitrage_report",
    "format_topic_report",
]
