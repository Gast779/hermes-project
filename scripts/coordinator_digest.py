#!/usr/bin/env python3
"""🧠 Coordinator Digest → Telegram #824.

Usage:
    python scripts/coordinator_digest.py
"""
from __future__ import annotations

import logging
import os

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    try:
        from coordination.deliver import deliver_coordinator_digest
        deliver_coordinator_digest()
    except Exception as e:
        log.error("Coordinator digest failed: %s", e)


if __name__ == "__main__":
    main()
