#!/usr/bin/env python3
"""Polymarket Topic Monitor — direct Telegram delivery (no Hermes footer)."""
import os, sys
sys.path.insert(0, "/tmp/hermes_project/hermes_project")

from polymarket_analyzer import PolymarketClient, TopicMonitor
from polymarket_analyzer.reporter import format_topic_report
from scripts.notify_telegram import send_telegram
from scripts.telegram_router import TelegramRouter

KEYWORD = os.getenv("TOPIC_KEYWORD", "trump")

if __name__ == "__main__":
    router = TelegramRouter()
    thread_id = router.get_topic_id("polymarket_topic_monitor")

    with PolymarketClient() as client:
        monitor = TopicMonitor(client, keyword=KEYWORD)
        report = monitor.tick()
        text = format_topic_report(report)

    if text.strip():
        send_telegram(text, message_thread_id=thread_id, parse_mode="Markdown")
