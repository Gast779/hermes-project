#!/usr/bin/env python3
"""🏦 Deribit basis scan → Telegram #827.

Usage: python scripts/deribit_scan.py [BTC|ETH]"""
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
    crypto = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    try:
        from deribit import get_deribit_analyzer
        a = get_deribit_analyzer()
        opps = a.find_basis_arbitrage()
        if opps:
            sig = opps[0]
            msg = (
                f"🎯 Deribit Basis {sig.symbol}\n"
                f"   Perp: ${sig.spot_price:,.0f}  Future: ${sig.futures_price:,.0f}\n"
                f"   Basis: {sig.basis_percent:.2f}%  Annualized: {sig.funding_rate_ann:.1f}%\n"
                f"   Funding: {sig.funding_rate_1h*100:.3f}%  Days: {sig.days_to_expiry}"
            )
            send(msg, 827)
            log.info("Sent Deribit signal")
        else:
            log.info("No Deribit signal")
    except Exception as e:
        log.error("Deribit scan failed: %s", e)


if __name__ == "__main__":
    main()
