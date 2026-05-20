"""
Lesson Planner.

Тримає у JSON-файлі профіль користувача:
    - CEFR-рівень,
    - пройдені теми (граматичні/лексичні),
    - історія занять (для spaced repetition).

Видає `Lesson` — структуру для виконання в боті.
"""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)


# CEFR-послідовність граматичних тем (спрощена програма)
GRAMMAR_SYLLABUS: dict[str, list[str]] = {
    "A1": [
        "to be (am/is/are)", "Present Simple — affirmative",
        "Present Simple — questions/negatives", "Articles a/an/the",
        "Plural nouns", "Possessives (my, your, his)",
    ],
    "A2": [
        "Present Continuous", "Present Simple vs Continuous",
        "Past Simple — regular", "Past Simple — irregular",
        "Future with going to / will", "Comparatives & superlatives",
    ],
    "B1": [
        "Present Perfect — for/since", "Past Continuous",
        "Past Simple vs Present Perfect", "First conditional",
        "Modal verbs: must / have to / should", "Relative clauses (who/which/that)",
    ],
    "B2": [
        "Present Perfect Continuous", "Past Perfect",
        "Second & third conditionals", "Passive voice — all tenses",
        "Reported speech", "Modal verbs of deduction (must/might/can't have)",
    ],
    "C1": [
        "Mixed conditionals", "Inversion (Hardly had I … / Never have I …)",
        "Cleft sentences", "Subjunctive (I wish / If only / It's time)",
        "Phrasal verbs — advanced", "Discourse markers",
    ],
}

VOCAB_TOPICS = [
    "daily routines", "food and drinks", "travel and transport",
    "work and office", "technology and IT", "cryptocurrency and trading",
    "feelings and emotions", "health and fitness", "news and politics",
    "movies and entertainment",
]


class LessonType(str, Enum):
    VOCABULARY = "vocabulary"
    GRAMMAR = "grammar"
    SPEAKING = "speaking"
    LISTENING = "listening"
    TRANSLATION = "translation"
    IMAGE = "image"


@dataclass
class Lesson:
    type: LessonType
    topic: str
    level: str
    instructions: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Profile:
    level: str = "B1"
    completed_grammar: list[str] = field(default_factory=list)
    completed_vocab: list[str] = field(default_factory=list)
    last_lesson_date: str | None = None
    streak_days: int = 0


# --------------------------------------------------------------------------- #
class LessonPlanner:
    def __init__(self, profile_path: Path | str = "~/.hermes/english_profile.json"):
        self.profile_path = Path(profile_path).expanduser()
        self.profile = self._load()

    # ---- persistence ----------------------------------------------------- #
    def _load(self) -> Profile:
        if self.profile_path.exists():
            with open(self.profile_path, "r", encoding="utf-8") as fh:
                try:
                    return Profile(**json.load(fh))
                except Exception as e:    # noqa: BLE001
                    log.warning("Profile load failed (%s); using defaults", e)
        return Profile()

    def save(self) -> None:
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self.profile), fh, ensure_ascii=False, indent=2)

    # ---- streak tracking ------------------------------------------------- #
    def _update_streak(self) -> None:
        today = date.today().isoformat()
        if self.profile.last_lesson_date == today:
            return                       # вже зараховано
        if self.profile.last_lesson_date:
            prev = date.fromisoformat(self.profile.last_lesson_date)
            delta = (date.today() - prev).days
            self.profile.streak_days = self.profile.streak_days + 1 if delta == 1 else 1
        else:
            self.profile.streak_days = 1
        self.profile.last_lesson_date = today

    # ---- planner --------------------------------------------------------- #
    def next_grammar_topic(self) -> str:
        syllabus = GRAMMAR_SYLLABUS.get(self.profile.level, GRAMMAR_SYLLABUS["B1"])
        for t in syllabus:
            if t not in self.profile.completed_grammar:
                return t
        # все пройдено — даємо випадковий для повторення
        return random.choice(syllabus)

    def plan(self, prefer: LessonType | None = None) -> Lesson:
        """Підібрати наступний урок."""
        self._update_streak()
        self.save()

        if prefer is None:
            # простий ротатор: 2 з 5 шансів — граматика, 2 — лексика, 1 — speaking
            prefer = random.choices(
                [LessonType.GRAMMAR, LessonType.GRAMMAR, LessonType.VOCABULARY,
                 LessonType.VOCABULARY, LessonType.SPEAKING],
                k=1,
            )[0]

        if prefer == LessonType.GRAMMAR:
            topic = self.next_grammar_topic()
            return Lesson(type=prefer, topic=topic, level=self.profile.level,
                          instructions=f"Грама-фокус: {topic}")

        if prefer == LessonType.VOCABULARY:
            unseen = [t for t in VOCAB_TOPICS if t not in self.profile.completed_vocab]
            topic = random.choice(unseen or VOCAB_TOPICS)
            return Lesson(type=prefer, topic=topic, level=self.profile.level,
                          instructions=f"Vocabulary: {topic}")

        if prefer == LessonType.SPEAKING:
            scenario = random.choice([
                "Order coffee at a café",
                "Explain to a colleague what you did yesterday",
                "Describe your last trip in 60 seconds",
                "React to a recent crypto market move",
                "Pitch your favourite hobby to a stranger",
            ])
            return Lesson(type=prefer, topic=scenario, level=self.profile.level,
                          instructions=f"Roleplay: {scenario}")

        return Lesson(type=prefer, topic="free chat", level=self.profile.level,
                      instructions="Open-ended conversation")

    def mark_completed(self, lesson: Lesson) -> None:
        if lesson.type == LessonType.GRAMMAR and lesson.topic not in self.profile.completed_grammar:
            self.profile.completed_grammar.append(lesson.topic)
        if lesson.type == LessonType.VOCABULARY and lesson.topic not in self.profile.completed_vocab:
            self.profile.completed_vocab.append(lesson.topic)
        self.save()
