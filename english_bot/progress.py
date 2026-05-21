"""
Прогрес-дашборд для English Bot.

Збирає дані з усіх підсистем:
    - english_profile.json    — уроки, streak
    - english_flashcards.json — SRS картки
    - english_quiz_log.json   — квізи
    - english_daily_log.json  — daily challenges
    - english_podcast_history.json — podcast sessions
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)


class ProgressDashboard:
    def __init__(self, base_dir: Path | str = "~/.hermes"):
        self.base = Path(base_dir).expanduser()
        self._sources = {
            "profile": self.base / "english_profile.json",
            "flashcards": self.base / "english_flashcards.json",
            "quiz": self.base / "english_quiz_log.json",
            "daily": self.base / "english_daily_log.json",
            "podcast": self.base / "english_podcast_history.json",
        }

    def _load(self, key: str) -> dict:
        path = self._sources.get(key)
        if not path or not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except Exception:
                return {}

    def build(self) -> dict:
        """Повернути повний дашборд у форматі dict."""
        profile = self._load("profile")
        flashcards = self._load("flashcards")
        quiz = self._load("quiz")
        daily = self._load("daily")
        podcast = self._load("podcast")

        # --- Lessons ------------------------------------------------------ #
        lessons_done = len(profile.get("completed_grammar", [])) + len(profile.get("completed_vocab", []))
        streak_lessons = profile.get("streak_days", 0)
        level = profile.get("level", "B1")

        # --- Flashcards --------------------------------------------------- #
        cards = flashcards.get("cards", {})
        total_cards = len(cards)
        mature = sum(1 for c in cards.values() if c.get("repetitions", 0) >= 3)
        today = date.today().isoformat()
        due_today = sum(1 for c in cards.values() if c.get("due_date", "") <= today)

        # --- Quiz --------------------------------------------------------- #
        quiz_log = quiz if isinstance(quiz, list) else []
        total_quizzes = len(quiz_log)
        avg_score = round(sum(s.get("score_pct", 0) for s in quiz_log) / total_quizzes, 1) if quiz_log else 0
        # accuracy по типах
        grammar_questions = []
        vocab_questions = []
        for session in quiz_log:
            for q in session.get("questions", []):
                if q.get("kind") == "grammar":
                    grammar_questions.append(q.get("correct", False))
                elif q.get("kind") == "vocab":
                    vocab_questions.append(q.get("correct", False))
        grammar_acc = round(100 * sum(grammar_questions) / len(grammar_questions), 1) if grammar_questions else None
        vocab_acc = round(100 * sum(vocab_questions) / len(vocab_questions), 1) if vocab_questions else None

        # --- Daily -------------------------------------------------------- #
        history = daily.get("history", [])
        total_challenges = len(history)
        completed_challenges = sum(1 for h in history if h.get("completed"))
        streak_daily = daily.get("streak", 0)

        # --- Podcast ------------------------------------------------------ #
        podcast_log = podcast if isinstance(podcast, list) else []
        total_podcasts = len(podcast_log)

        # --- Weak spots --------------------------------------------------- #
        weak_grammar = self._find_weak_grammar(grammar_questions, quiz_log)

        return {
            "level": level,
            "lessons": {
                "completed": lessons_done,
                "streak": streak_lessons,
            },
            "flashcards": {
                "total": total_cards,
                "mature": mature,
                "due_today": due_today,
            },
            "quizzes": {
                "total_sessions": total_quizzes,
                "avg_score": avg_score,
                "grammar_accuracy": grammar_acc,
                "vocab_accuracy": vocab_acc,
            },
            "daily": {
                "total": total_challenges,
                "completed": completed_challenges,
                "streak": streak_daily,
                "completion_rate": round(100 * completed_challenges / total_challenges, 1) if total_challenges else 0,
            },
            "podcasts": {
                "total": total_podcasts,
            },
            "weak_spots": weak_grammar,
        }

    @staticmethod
    def _find_weak_grammar(grammar_results: list[bool], quiz_log: list[dict]) -> list[str]:
        """
        Проста евристика: якщо accuracy по граматиці < 70%,
        беремо назву останньої граматичної теми з уроків.
        """
        if not grammar_results:
            return []
        accuracy = sum(grammar_results) / len(grammar_results)
        if accuracy >= 0.7:
            return []
        # знайти останню граматичну тему
        for session in reversed(quiz_log):
            for q in reversed(session.get("questions", [])):
                if q.get("kind") == "grammar":
                    # повертаємо перші 3 слова як "тему" (хеуристично)
                    words = q.get("q", "").split()[:3]
                    return [" ".join(words) + " — потрібно повторити"]
        return []
