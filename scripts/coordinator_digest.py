#!/usr/bin/env python3
"""Wrapper: run coordinator digest generation + delivery."""
from __future__ import annotations

import logging
import os

logging.basicConfig(level=logging.INFO)

from coordination.coordinator import get_coordinator

def main() -> None:
    coord = get_coordinator()
    coord.publish_digest()
    print("✅ Coordinator digest published to event bus")

    # Also try Telegram delivery
    try:
        from coordination.deliver import deliver_coordinator_digest
        deliver_coordinator_digest()
    except Exception as e:
        print(f"⚠️ Telegram delivery skipped: {e}")

if __name__ == "__main__":
    main()
