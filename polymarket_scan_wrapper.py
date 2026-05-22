#!/usr/bin/env python
"""Wrapper: scan Polymarket, print report or "no arbitrage" msg."""
from __future__ import annotations

import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from polymarket_analyzer import InternalArbitrageFinder, PolymarketClient, format_arbitrage_report

opps = []
with PolymarketClient() as client:
    finder = InternalArbitrageFinder(client, min_edge=0.01, min_volume_usd=1000.0)
    opps = finder.find(max_markets=10)

if opps:
    report = format_arbitrage_report(opps)
    print(report)
else:
    print("🔍 Сканування завершено. Арбітраж не знайдено.")
