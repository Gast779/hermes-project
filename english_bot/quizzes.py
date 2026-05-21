"""
Інтерактивні квізи для English Bot.

Типи:
    - grammar: вибір правильної граматичної форми
    - vocab:   переклад з української / англійської
    - mixed:   поєднання обох

Питання генерує Grok у форматі JSON (для точності). Бали трекаються у
~/.hermes/english_quiz_log.json.
"""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

from .grok_client import GrokClient
from .prompts import SYSTEM_TUTOR

log = logging.getLogger(__name__)

QuizKind = Literal["grammar", "vocab", "mixed"]


@dataclass
class Question:
    id: int
    kind: str            # "grammar" | "vocab"
    question: str
    options: list[str]   # 4 варіанти (один правильний)
    correct_index: int   # 0..3
    explanation: str     # українською — чому саме так


@dataclass
class QuizSession:
    started_at: str
    kind: str
    questions: list[Question]
    answers: list[dict]  # [{"qid": int, "choice": int, "correct": bool, "time_ms": int}]


class QuizEngine:
    def __init__(self, grok: GrokClient, level: str = "B1"):
        self.grok = grok
        self.level = level
        self.log_path = Path("~/.hermes/english_quiz_log.json").expanduser()

    # ---- persistence ---------------------------------------------------- #
    def _load_log(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        with open(self.log_path, "r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except Exception:
                return []

    def _save_log(self, entries: list[dict]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, ensure_ascii=False, indent=2)

    def _append_session(self, session: QuizSession) -> None:
        log_data = self._load_log()
        correct = sum(1 for a in session.answers if a["correct"])
        total = len(session.answers)
        log_data.append({
            "date": session.started_at,
            "kind": session.kind,
            "total": total,
            "correct": correct,
            "score_pct": round(100 * correct / total, 1) if total else 0,
            "questions": [
                {
                    "q": q.question,
                    "kind": q.kind,
                    "correct": any(
                        a["qid"] == q.id and a["correct"]
                        for a in session.answers
                    ),
                }
                for q in session.questions
            ],
        })
        self._save_log(log_data)

    # ---- generation ----------------------------------------------------- #
    def generate_questions(self, kind: QuizKind, count: int = 5) -> list[Question]:
        system = SYSTEM_TUTOR.format(level=self.level)
        if kind == "grammar":
            user_prompt = (
                f"Generate {count} multiple-choice grammar questions for CEFR {self.level}.\n"
                "Each question must have:\n"
                "  - question (string)\n"
                "  - options (array of 4 strings)\n"
                "  - correct_index (integer 0..3)\n"
                "  - explanation (string in Ukrainian)\n"
                "Return ONLY a valid JSON array. No markdown wrappers, no comments."
            )
        elif kind == "vocab":
            user_prompt = (
                f"Generate {count} vocabulary multiple-choice questions for CEFR {self.level}.\n"
                "Mix Ukrainian→English and English→Ukrainian.\n"
                "Each question must have:\n"
                "  - question (string)\n"
                "  - options (array of 4 strings)\n"
                "  - correct_index (integer 0..3)\n"
                "  - explanation (string in Ukrainian)\n"
                "Return ONLY a valid JSON array. No markdown wrappers, no comments."
            )
        else:
            user_prompt = (
                f"Generate {count} mixed grammar+vocabulary multiple-choice questions for CEFR {self.level}.\n"
                "Each question must have:\n"
                "  - kind: 'grammar' or 'vocab'\n"
                "  - question (string)\n"
                "  - options (array of 4 strings)\n"
                "  - correct_index (integer 0..3)\n"
                "  - explanation (string in Ukrainian)\n"
                "Return ONLY a valid JSON array. No markdown wrappers, no comments."
            )

        raw = self.grok.chat_simple(system, user_prompt)
        return self._parse_questions(raw, kind)

    def _parse_questions(self, raw: str, default_kind: str) -> list[Question]:
        import re
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            log.error("Grok quiz response did not contain JSON array. Raw: %s", raw[:500])
            raise ValueError("Grok повернув не JSON. Спробуй ще раз.")
        data = json.loads(m.group())
        questions = []
        for i, item in enumerate(data, start=1):
            q = Question(
                id=i,
                kind=item.get("kind", default_kind),
                question=item["question"],
                options=item["options"],
                correct_index=item["correct_index"],
                explanation=item["explanation"],
            )
            # Перемішуємо опції, зберігаючи correct_index
            q = self._shuffle_options(q)
            questions.append(q)
        return questions

    @staticmethod
    def _shuffle_options(q: Question) -> Question:
        correct_text = q.options[q.correct_index]
        opts = q.options.copy()
        random.shuffle(opts)
        new_index = opts.index(correct_text)
        return Question(
            id=q.id,
            kind=q.kind,
            question=q.question,
            options=opts,
            correct_index=new_index,
            explanation=q.explanation,
        )

    # ---- session -------------------------------------------------------- #
    def start(self, kind: QuizKind, count: int = 5) -> QuizSession:
        questions = self.generate_questions(kind, count)
        return QuizSession(
            started_at=datetime.utcnow().isoformat(),
            kind=kind,
            questions=questions,
            answers=[],
        )

    def record_answer(self, session: QuizSession, qid: int, choice: int) -> tuple[bool, str]:
        q = next((q for q in session.questions if q.id == qid), None)
        if q is None:
            raise ValueError(f"Question {qid} not found")
        correct = choice == q.correct_index
        session.answers.append({
            "qid": qid,
            "choice": choice,
            "correct": correct,
            "time_ms": 0,   # можна додати таймер пізніше
        })
        return correct, q.explanation

    def finish(self, session: QuizSession) -> dict:
        self._append_session(session)
        correct = sum(1 for a in session.answers if a["correct"])
        total = len(session.answers)
        return {
            "total": total,
            "correct": correct,
            "score_pct": round(100 * correct / total, 1) if total else 0,
        }

    # ---- stats ---------------------------------------------------------- #
    def stats(self) -> dict:
        log_data = self._load_log()
        if not log_data:
            return {"total_sessions": 0}
        total_sessions = len(log_data)
        avg_score = round(sum(s["score_pct"] for s in log_data) / total_sessions, 1)
        grammar_pct = self._kind_accuracy(log_data, "grammar")
        vocab_pct = self._kind_accuracy(log_data, "vocab")
        return {
            "total_sessions": total_sessions,
            "avg_score": avg_score,
            "grammar_accuracy": grammar_pct,
            "vocab_accuracy": vocab_pct,
            "last_session": log_data[-1]["date"][:10] if log_data else None,
        }

    @staticmethod
    def _kind_accuracy(log_data: list[dict], kind: str) -> float | None:
        relevant = []
        for session in log_data:
            for q in session.get("questions", []):
                if q.get("kind") == kind:
                    relevant.append(q["correct"])
        if not relevant:
            return None
        return round(100 * sum(relevant) / len(relevant), 1)
