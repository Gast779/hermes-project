#!/usr/bin/env python3
"""🐳 On-chain whale check → Telegram #828.

Usage: python scripts/onchain_whales.py [BTC|ETH|All]"""
from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def send(msg: str, thread_id: int) -> None:
    import requests
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_HOME_CHANNEL", "934870074")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat,
            "text": msg,
            "message_thread_id": thread_id,
            "parse_mode": "Markdown",
        }, timeout=10)
    except Exception as e:
        log.warning("Telegram send failed: %s", e)


def main() -> None:
    crypto_arg = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    try:
        from strategies.onchain_monitor import get_monitor
        m = get_monitor()
        if crypto_arg.lower() == "all":
            for c in ["BTC", "ETH"]:
                m.detect_large_transactions(c)
                log.info("Checked whales for %s", c)
        else:
            m.detect_large_transactions(crypto_arg)
            log.info("Checked whales for %s", crypto_arg)
    except Exception as e:
        log.error("On-chain whale check failed: %s", e)


if __name__ == "__main__":
    main()
