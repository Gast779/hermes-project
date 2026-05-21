"""
Listening / Podcast mode для English Bot.

Генерує через Grok діалог на тему (2 персонажі обговорюють крипто / IT / новини),
після якого йдуть comprehension-питання.

Аналог Audio Overview з NotebookLM, але текстовий формат (без TTS поки).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from .grok_client import GrokClient
from .prompts import SYSTEM_TUTOR

log = logging.getLogger(__name__)

PodcastLevel = Literal["A2", "B1", "B2", "C1"]


@dataclass
class PodcastScript:
    title: str
    level: str
    topic: str
    dialog: list[dict]          # [{"speaker": "Alex", "text": "..."}]
    vocabulary: list[dict]      # [{"word": "...", "ipa": "...", "uk": "..."}]
    questions: list[dict]       # [{"question": "...", "options": [...], "correct": int}]


class PodcastEngine:
    def __init__(self, grok: GrokClient, level: str = "B1"):
        self.grok = grok
        self.level = level
        self.history_path = Path("~/.hermes/english_podcast_history.json").expanduser()

    def generate(self, topic: str | None = None, n_questions: int = 3) -> PodcastScript:
        """Згенерувати діалог + comprehension questions."""
        topic = topic or self._random_topic()
        system = SYSTEM_TUTOR.format(level=self.level)
        user = (
            f"Create a short podcast-style dialogue (CEFR {self.level}) on the topic: \"{topic}\".\n\n"
            "Format: two speakers (Alex & Jordan) having a natural conversation.\n"
            "Requirements:\n"
            "  - 6-10 turns total\n"
            "  - Use natural, conversational English\n"
            "  - Include 1-2 idioms or phrasal verbs\n\n"
            "After the dialogue, provide:\n"
            f"  - {n_questions} multiple-choice comprehension questions\n"
            "  - 5 key vocabulary items with IPA and Ukrainian translation\n\n"
            "Return ONLY valid JSON with this structure:\n"
            '{\n'
            '  "title": "...",\n'
            '  "dialog": [{"speaker": "Alex", "text": "..."}, ...],\n'
            '  "vocabulary": [{"word": "...", "ipa": "...", "uk": "..."}, ...],\n'
            '  "questions": [{"question": "...", "options": ["...", "...", "...", "..."], "correct": 0}, ...]\n'
            '}\n'
            "No markdown, no comments."
        )
        raw = self.grok.chat_simple(system, user)
        return self._parse(raw, topic)

    def _parse(self, raw: str, topic: str) -> PodcastScript:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            log.error("Podcast response has no JSON. Raw: %s", raw[:500])
            raise ValueError("Grok не повернув JSON. Спробуй іншу тему.")
        data = json.loads(m.group())
        return PodcastScript(
            title=data.get("title", topic),
            level=self.level,
            topic=topic,
            dialog=data.get("dialog", []),
            vocabulary=data.get("vocabulary", []),
            questions=data.get("questions", []),
        )

    @staticmethod
    def _random_topic() -> str:
        import random
        topics = [
            "the future of AI in finance",
            "remote work vs office culture",
            "cryptocurrency regulations",
            "why learning English matters for developers",
            "the psychology of trading decisions",
            "how social media changes news consumption",
            "sustainable technology",
            "the gig economy",
        ]
        return random.choice(topics)

    def save_to_history(self, script: PodcastScript) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if self.history_path.exists():
            with open(self.history_path, "r", encoding="utf-8") as fh:
                try:
                    history = json.load(fh)
                except Exception:
                    history = []
        entry = {
            "date": datetime.utcnow().isoformat(),
            "title": script.title,
            "topic": script.topic,
            "level": script.level,
        }
        history.append(entry)
        with open(self.history_path, "w", encoding="utf-8") as fh:
            json.dump(history, fh, ensure_ascii=False, indent=2)
