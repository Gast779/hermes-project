#!/usr/bin/env python3
"""📈 LP yield scan → Telegram #827.

Usage: python scripts/lp_scan.py [ethereum|arbitrum|polygon|bsc]"""
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
    chain = sys.argv[1] if len(sys.argv) > 1 else "ethereum"
    try:
        from lp_yield import get_lp_scanner
        scanner = get_lp_scanner()
        pools = scanner.get_pools(min_tvl=1_000_000)
        for p in pools[:2]:
            scanner.publish_pool(p)
        top = pools[:3]
        if top:
            msg = f"📈 LP Scan ({chain})\n" + "\n".join(
                f"   {i+1}. {_.name}: {_.apy * 100:.2f}% APY | TVL ${_.tvl_usd:,.0f}"
                for i, _ in enumerate(top)
            )
            send(msg, 827)
            log.info("Sent LP scan")
        else:
            log.info("No LP pools")
    except Exception as e:
        log.error("LP scan failed: %s", e)


if __name__ == "__main__":
    main()
