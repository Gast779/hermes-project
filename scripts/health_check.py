#!/usr/bin/env python3
"""🏥 System health check → Telegram #828 (на помилку).

Usage: python scripts/health_check.py"""
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
    try:
        from safety.health import get_health
        h = get_health()
        r = h.check_component("all")
        if r.status == "error":
            send(f"🚨 Health failure: {r.component} — {r.details}", 828)
            log.warning("Health error reported")
        else:
            log.info("Health OK")
    except Exception as e:
        log.error("Health check failed: %s", e)


if __name__ == "__main__":
    main()
