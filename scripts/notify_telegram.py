"""
Простий синхронний нотифікатор у Telegram.
Не використовуємо python-telegram-bot, щоб не тягнути зайвої залежності.
"""
from __future__ import annotations

import logging
import os
from typing import Final

import httpx

log = logging.getLogger(__name__)

_API_TPL: Final = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(
    text: str,
    *,
    parse_mode: str = "Markdown",
    chat_id: str | None = None,
    message_thread_id: int | None = None,
) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not chat_id:
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("Telegram credentials missing; skipping notification.")
        return False
    # Telegram має ліміт 4096 символів на повідомлення
    if len(text) > 4000:
        text = text[:3990] + "\n…(truncated)"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": "true",
    }
    if message_thread_id is not None:
        payload["message_thread_id"] = str(message_thread_id)
    try:
        r = httpx.post(
            _API_TPL.format(token=token),
            data=payload,
            timeout=10.0,
        )
        r.raise_for_status()
        return True
    except httpx.HTTPError as e:
        log.warning("Telegram send failed: %s", e)
        return False
