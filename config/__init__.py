"""Загальні налаштування проєкту: читає .env + settings.yaml."""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    """Параметри з settings.yaml (кешуємо — читається 1 раз за процес)."""
    with open(ROOT / "config" / "settings.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def env(name: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.getenv(name, default)
    if required and not val:
        raise RuntimeError(f"Environment variable {name} is required but not set.")
    return val


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


__all__ = ["settings", "env", "setup_logging", "ROOT"]
