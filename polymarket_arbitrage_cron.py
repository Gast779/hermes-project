#!/usr/bin/env python
"""Сканувати Polymarket на арбітраж і надсилати результат у Telegram topic."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
import os

dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

from polymarket_analyzer import InternalArbitrageFinder, PolymarketClient, format_arbitrage_report
from scripts.notify_telegram import send_telegram

CHAT_ID = "-1003792129186"
THREAD_ID = 27

def main() -> None:
    opps = []
    with PolymarketClient() as client:
        finder = InternalArbitrageFinder(client, min_edge=0.01, min_volume_usd=1000.0)
        opps = finder.find(max_markets=10)

    if opps:
        report = format_arbitrage_report(opps)
        send_telegram(report, chat_id=CHAT_ID, message_thread_id=THREAD_ID)
        print(report)
    else:
        msg = "🔍 Сканування завершено. Арбітраж не знайдено."
        send_telegram(msg, chat_id=CHAT_ID, message_thread_id=THREAD_ID)
        print(msg)

if __name__ == "__main__":
    main()
