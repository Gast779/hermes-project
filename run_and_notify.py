#!/usr/bin/env python3
"""Run Polymarket scan and send results to Telegram topic."""
import sys, os
from pathlib import Path
sys.path.insert(0, '/tmp/hermes_project/hermes_project')

# Load .env files, global overrides project so env vars are usable
from dotenv import load_dotenv
load_dotenv('/tmp/hermes_project/hermes_project/.env')
load_dotenv('/home/hermes/.hermes/.env', override=True)

from polymarket_analyzer import (
    PolymarketClient,
    InternalArbitrageFinder,
    format_arbitrage_report,
)
from scripts.notify_telegram import send_telegram

CHAT_ID = "-1003792129186"
THREAD_ID = 27
MAX_MARKETS = 10
MIN_EDGE = 0.01
MIN_VOLUME = 1000.0

with PolymarketClient() as client:
    finder = InternalArbitrageFinder(client, min_edge=MIN_EDGE, min_volume_usd=MIN_VOLUME)
    opps = finder.find(max_markets=MAX_MARKETS)

report = format_arbitrage_report(opps)
print(report if report else "[NO ARBITRAGE]")

if opps and report.strip():
    ok = send_telegram(report, chat_id=CHAT_ID, message_thread_id=THREAD_ID)
    print("STATUS: sent" if ok else "STATUS: failed")
else:
    msg = "🔍 Сканування завершено. Арбітраж не знайдено."
    ok = send_telegram(msg, chat_id=CHAT_ID, message_thread_id=THREAD_ID)
    print("STATUS: sent (no arb)" if ok else "STATUS: failed (no arb)")
