"""
Deliver Coordinator Digest to Telegram.

Thread: #31 (coordinator_digest)
Schedule: кожні 4 години
"""

from __future__ import annotations

import logging
import os

from coordination.coordinator import get_coordinator

log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "-1003792129186")
CO_TOPIC = 31  # coordinator_digest


def deliver_coordinator_digest() -> None:
    """Згенерувати і відправити coordinator digest у Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set, skipping digest delivery")
        return

    try:
        import requests
    except ImportError:
        log.error("requests not installed")
        return

    coord = get_coordinator()
    text = coord.generate_digest()

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_GROUP_ID,
        "message_thread_id": CO_TOPIC,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        log.info("Coordinator digest delivered to topic %d", CO_TOPIC)
    except Exception as e:
        log.error("Failed to deliver digest: %s", e)


if __name__ == "__main__":
    deliver_coordinator_digest()
