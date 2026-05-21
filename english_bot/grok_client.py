"""
Тонкий клієнт до xAI Grok через OpenAI-сумісний endpoint.

base_url = https://api.x.ai/v1
Auth     = Bearer {XAI_API_KEY}

Працює з openai>=1.40.
"""
from __future__ import annotations

import base64
import logging
from typing import Iterable

from openai import OpenAI

log = logging.getLogger(__name__)


class GrokClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = "grok-4-0709",
        base_url: str = "https://api.x.ai/v1",
        timeout: float = 60.0,
    ):
        import os
        if api_key is None:
            api_key = os.getenv("XAI_API_KEY", "")
        if not api_key:
            raise ValueError("XAI_API_KEY is required for GrokClient. Set it in .env or pass to constructor.")
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    # ---- text ------------------------------------------------------------ #
    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.6,
        max_tokens: int = 800,
        model: str | None = None,
    ) -> str:
        """messages у OpenAI-форматі: [{role: system|user|assistant, content: str}]"""
        resp = self._client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def chat_simple(self, system: str, user: str, **kw) -> str:
        try:
            return self.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                **kw,
            )
        except Exception as e:
            log.warning("Grok API error: %s", e)
            return (
                "⚠️ **XAI API Error**\n\n"
                f"_{str(e)}_\n\n"
                "**Щоб використовувати English Bot:**\n"
                "1. Отримай API ключ на https://console.x.ai\n"
                "2. Додай його в `.env`: `XAI_API_KEY=sk-...`\n\n"
                "**English Bot — це персональний тренер англійської на базі Grok.**\n"
                "Вміє: генерувати уроки граматики/лексики, рольові ігри, \n"
                "перевіряти переклади, аналізувати голосові повідомлення."
            )

    # ---- image ----------------------------------------------------------- #
    def chat_with_image(
        self,
        system: str,
        user_text: str,
        image_bytes: bytes,
        *,
        image_mime: str = "image/jpeg",
        temperature: float = 0.5,
        max_tokens: int = 800,
    ) -> str:
        """
        Grok vision: за документацією моделі типу `grok-4-vision`, `grok-2-vision-1212`.
        Передаємо base64.
        """
        b64 = base64.b64encode(image_bytes).decode("ascii")
        return self.chat(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{image_mime};base64,{b64}"},
                        },
                    ],
                },
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            model="grok-2-vision-1212",   # дешевша vision-модель; можна змінити
        )

    # ---- audio ----------------------------------------------------------- #
    def transcribe(self, audio_bytes: bytes, language_hint: str | None = None) -> str:
        """
        Grok не має власного STT.  Тут поки заглушка — у production підключаємо
        Whisper API (OpenAI) або локальний faster-whisper.
        """
        raise NotImplementedError(
            "STT для голосових повідомлень потрібно підключити окремо. "
            "Рекомендується OpenAI Whisper API або faster-whisper."
        )
