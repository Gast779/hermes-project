"""
Spaced Repetition Flashcards (SRS) для English Bot.

Спрощений алгоритм SM-2:
    again (0) → 1 день, repetitions = 0
    hard  (1) → max(2, interval * 1.2) днів
    good  (2) → max(3, interval * ease_factor) днів
    easy  (3) → max(7, interval * (ease_factor + 0.3)) днів

ease_factor мінімум 1.3.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

Rating = Literal[0, 1, 2, 3]

RATING_LABELS: dict[int, str] = {
    0: "🔴 Не знаю",
    1: "🟠 Важко",
    2: "🟢 Добре",
    3: "🔵 Легко",
}


@dataclass
class Flashcard:
    id: str
    front: str           # українське слово/фраза
    back: str            # англійське слово/фраза
    ipa: str             # транскрипція
    example: str         # приклад речення (EN)
    example_uk: str      # переклад прикладу
    level: str
    tags: list[str]
    due_date: str        # YYYY-MM-DD
    interval: int        # днів
    repetitions: int     # успішних повторень підряд
    ease_factor: float   # коефіцієнт легкості
    created_at: str
    history: list[dict] = field(default_factory=list)

    def is_due(self, today: date | None = None) -> bool:
        today = today or date.today()
        return date.fromisoformat(self.due_date) <= today


class FlashcardDeck:
    def __init__(self, path: Path | str = "~/.hermes/english_flashcards.json"):
        self.path = Path(path).expanduser()
        self.cards: dict[str, Flashcard] = {}
        self._load()

    # ---- persistence ---------------------------------------------------- #
    def _load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            try:
                raw = json.load(fh)
            except Exception as e:
                log.warning("Flashcards load failed (%s); starting fresh", e)
                return
        for cid, data in raw.get("cards", {}).items():
            try:
                self.cards[cid] = Flashcard(**data)
            except Exception as e:
                log.warning("Skipping corrupted card %s: %s", cid, e)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cards": {cid: asdict(card) for cid, card in self.cards.items()},
            "meta": {
                "saved_at": datetime.utcnow().isoformat(),
                "total": len(self.cards),
            },
        }
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    # ---- CRUD ----------------------------------------------------------- #
    def add(
        self,
        front: str,
        back: str,
        ipa: str = "",
        example: str = "",
        example_uk: str = "",
        level: str = "B1",
        tags: list[str] | None = None,
    ) -> Flashcard:
        cid = str(uuid.uuid4())[:8]
        card = Flashcard(
            id=cid,
            front=front,
            back=back,
            ipa=ipa,
            example=example,
            example_uk=example_uk,
            level=level,
            tags=tags or [],
            due_date=date.today().isoformat(),
            interval=0,
            repetitions=0,
            ease_factor=2.5,
            created_at=datetime.utcnow().isoformat(),
        )
        self.cards[cid] = card
        self.save()
        log.info("Added flashcard %s: %s → %s", cid, front, back)
        return card

    def get(self, cid: str) -> Flashcard | None:
        return self.cards.get(cid)

    def due_cards(self, today: date | None = None) -> list[Flashcard]:
        today = today or date.today()
        return sorted(
            [c for c in self.cards.values() if c.is_due(today)],
            key=lambda c: (c.repetitions, c.due_date),
        )

    def review(self, cid: str, rating: int) -> Flashcard | None:
        """
        rating: 0=again, 1=hard, 2=good, 3=easy
        Повертає оновлену картку.
        """
        card = self.cards.get(cid)
        if card is None:
            return None

        today = date.today()
        old_interval = card.interval

        if rating == 0:          # again
            card.interval = 1
            card.repetitions = 0
            card.ease_factor = max(1.3, card.ease_factor - 0.2)
        elif rating == 1:        # hard
            card.interval = max(2, int(old_interval * 1.2))
            card.repetitions += 1
            card.ease_factor = max(1.3, card.ease_factor - 0.15)
        elif rating == 2:        # good
            card.interval = max(3, int(old_interval * card.ease_factor))
            card.repetitions += 1
        elif rating == 3:        # easy
            card.interval = max(7, int(old_interval * (card.ease_factor + 0.3)))
            card.repetitions += 1
            card.ease_factor += 0.15
        else:
            raise ValueError(f"Invalid rating {rating}; use 0-3")

        card.due_date = (today + timedelta(days=card.interval)).isoformat()
        card.history.append({
            "date": today.isoformat(),
            "rating": rating,
            "interval": card.interval,
        })
        self.save()
        log.info("Reviewed card %s: rating=%s interval=%d", cid, rating, card.interval)
        return card

    # ---- stats ---------------------------------------------------------- #
    def stats(self) -> dict:
        today = date.today()
        due = [c for c in self.cards.values() if c.is_due(today)]
        new_cards = [c for c in due if c.repetitions == 0]
        review_cards = [c for c in due if c.repetitions > 0]
        mature = [c for c in self.cards.values() if c.repetitions >= 3]
        return {
            "total": len(self.cards),
            "due_today": len(due),
            "new": len(new_cards),
            "review": len(review_cards),
            "mature": len(mature),
        }
