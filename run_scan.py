#!/usr/bin/env python3
"""Wrapper for polymarket scan that produces plain text output."""
import json
import sys
sys.path.insert(0, '/tmp/hermes_project/hermes_project')

from polymarket_analyzer.client import PolymarketClient
from polymarket_analyzer.arbitrage_internal import InternalArbitrageFinder
from polymarket_analyzer.reporter import format_arbitrage_report

MAX_MARKETS = 10
MIN_EDGE = 0.01
MIN_VOLUME = 1000.0

with PolymarketClient() as client:
    finder = InternalArbitrageFinder(client, min_edge=MIN_EDGE, min_volume_usd=MIN_VOLUME)
    opps = finder.find(max_markets=MAX_MARKETS)

report = format_arbitrage_report(opps)

result = {
    "found": bool(opps),
    "count": len(opps),
    "report": report,
    "opps": [o.to_dict() for o in opps],
}

print(json.dumps(result, ensure_ascii=False, indent=2))
