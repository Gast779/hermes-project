#!/usr/bin/env python3
import os, sys
sys.path.insert(0, '/tmp/hermes_project/hermes_project')

# Ensure token from shell is preserved
print("TOKEN present?" , bool(os.getenv("TELEGRAM_BOT_TOKEN")))

from polymarket_analyzer import InternalArbitrageFinder, PolymarketClient, format_arbitrage_report
from scripts.notify_telegram import send_telegram

CHAT_ID = "-1003792129186"
THREAD_ID = 27

opps = []
with PolymarketClient() as client:
    finder = InternalArbitrageFinder(client, min_edge=0.01, min_volume_usd=1000.0)
    opps = finder.find(max_markets=10)

if opps:
    report = format_arbitrage_report(opps)
    ok = send_telegram(report, chat_id=CHAT_ID, message_thread_id=THREAD_ID)
    print("SEND_OK:", ok)
else:
    msg = "🔍 Сканування завершено. Арбітраж не знайдено."
    ok = send_telegram(msg, chat_id=CHAT_ID, message_thread_id=THREAD_ID)
    print("SEND_OK:", ok)
