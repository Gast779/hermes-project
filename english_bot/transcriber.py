"""
Speech-to-text для англійського бота.

Два бекенди:
    - "openai"          — OpenAI Whisper API (`whisper-1`).  Швидко, $0.006/min.
                          Працює одразу, потрібен лише OPENAI_API_KEY.
    - "faster-whisper"  — локальний faster-whisper.  Безкоштовно, але потребує
                          встановити `pip install faster-whisper` і ~150MB
                          моделі (base) або 1.5GB (large-v3).

Якщо обраний бекенд недоступний (бракує ключа/бібліотеки) — кидаємо
зрозумілу помилку, а не падаємо при імпорті.
"""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

Backend = Literal["openai", "faster-whisper"]


class Transcriber:
    """
    Універсальний інтерфейс. Викликай Transcriber(...).transcribe(audio).
    `audio` може бути bytes, path or file-like object.
    """

    def __init__(
        self,
        backend: Backend = "openai",
        *,
        model: str | None = None,
        language: str | None = None,    # 'en', 'uk' — або None для auto
    ):
        self.backend = backend
        self.language = language
        if backend == "openai":
            self.model = model or "whisper-1"
            self._init_openai()
        elif backend == "faster-whisper":
            self.model = model or "base"
            self._init_faster_whisper()
        else:
            raise ValueError(f"Unknown backend: {backend!r}")

    # ---- backend init ---------------------------------------------------- #
    def _init_openai(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set — потрібен для backend='openai'. "
                "Або встанови ключ, або обери backend='faster-whisper'."
            )
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("openai package required for backend='openai'") from e
        self._openai = OpenAI(api_key=api_key)

    def _init_faster_whisper(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "faster-whisper not installed. Run: pip install faster-whisper"
            ) from e
        # int8 — компроміс швидкість/якість на CPU
        self._fw = WhisperModel(self.model, device="auto", compute_type="int8")

    # ---- main API -------------------------------------------------------- #
    def transcribe(self, audio: bytes | str | Path | io.IOBase) -> str:
        if self.backend == "openai":
            return self._openai_transcribe(audio)
        return self._fw_transcribe(audio)

    # -- openai ----------------------------------------------------------- #
    def _openai_transcribe(self, audio) -> str:
        # OpenAI API чекає file-like з name (для визначення формату)
        if isinstance(audio, (str, Path)):
            f = open(audio, "rb")
            close_after = True
        elif isinstance(audio, bytes):
            f = io.BytesIO(audio)
            f.name = "audio.ogg"            # OpenAI визначає тип за розширенням
            close_after = False
        else:
            f = audio
            close_after = False
        try:
            kwargs = {"model": self.model, "file": f}
            if self.language:
                kwargs["language"] = self.language
            resp = self._openai.audio.transcriptions.create(**kwargs)
            return (resp.text or "").strip()
        finally:
            if close_after:
                f.close()

    # -- faster-whisper --------------------------------------------------- #
    def _fw_transcribe(self, audio) -> str:
        if isinstance(audio, bytes):
            # faster-whisper не приймає bytes напряму — пишемо у tempfile
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp.write(audio)
                tmp_path = tmp.name
            try:
                segments, _ = self._fw.transcribe(tmp_path, language=self.language)
                return " ".join(s.text for s in segments).strip()
            finally:
                os.unlink(tmp_path)
        if isinstance(audio, Path):
            audio = str(audio)
        segments, _ = self._fw.transcribe(audio, language=self.language)
        return " ".join(s.text for s in segments).strip()
