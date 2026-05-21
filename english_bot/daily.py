"""
Щоденний челлендж для English Bot.

Генерує одне завдання на день: переклад, граматика, fill-in-gap, rephrase.
Трекає streak: виконано сьогодні → +1 до серії, пропустив → скидається.
Бали зберігаються у ~/.hermes/english_daily_log.json.
"""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .grok_client import GrokClient
from .prompts import SYSTEM_TUTOR

log = logging.getLogger(__name__)


@dataclass
class DailyChallenge:
    date: str          # YYYY-MM-DD
    kind: str          # "translate" | "grammar" | "rephrase" | "vocab_fill"
    task: str          # завдання (українською / англійською)
    answer: str        # правильна відповідь
    explanation: str   # пояснення українською
    hint: str          # підказка


class DailyEngine:
    def __init__(self, grok: GrokClient, level: str = "B1"):
        self.grok = grok
        self.level = level
        self.log_path = Path("~/.hermes/english_daily_log.json").expanduser()

    # ---- persistence ---------------------------------------------------- #
    def _load_log(self) -> dict:
        if not self.log_path.exists():
            return {"streak": 0, "last_date": None, "history": []}
        with open(self.log_path, "r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except Exception:
                return {"streak": 0, "last_date": None, "history": []}

    def _save_log(self, data: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    # ---- streak --------------------------------------------------------- #
    def streak(self) -> dict:
        log_data = self._load_log()
        today = date.today().isoformat()
        last = log_data.get("last_date")
        if last == today:
            status = "done"
        elif last == (date.today() - __import__("datetime").timedelta(days=1)).isoformat():
            status = "active"  # стрик не зірвано, але сьогодні ще не виконано
        else:
            status = "broken"
        return {
            "streak": log_data.get("streak", 0),
            "status": status,
            "last_date": last,
        }

    def _update_streak(self, completed: bool) -> None:
        log_data = self._load_log()
        today = date.today().isoformat()
        last = log_data.get("last_date")
        if completed:
            if last == today:
                return  # вже зараховано
            if last == (date.today() - __import__("datetime").timedelta(days=1)).isoformat():
                log_data["streak"] = log_data.get("streak", 0) + 1
            else:
                log_data["streak"] = 1
            log_data["last_date"] = today
        self._save_log(log_data)

    # ---- generation ----------------------------------------------------- #
    def generate(self) -> DailyChallenge:
        today = date.today().isoformat()
        log_data = self._load_log()
        # перевірка чи вже генерували сьогодні
        for entry in log_data.get("history", []):
            if entry.get("date") == today:
                return DailyChallenge(
                    date=entry["date"],
                    kind=entry["kind"],
                    task=entry["task"],
                    answer=entry["answer"],
                    explanation=entry["explanation"],
                    hint=entry.get("hint", ""),
                )

        kind = random.choice(["translate", "grammar", "rephrase", "vocab_fill"])
        system = SYSTEM_TUTOR.format(level=self.level)
        if kind == "translate":
            user = (
                f"Generate ONE Ukrainian→English translation challenge for CEFR {self.level}.\n"
                "Return JSON: {\"task\": \"...\", \"answer\": \"...\", \"explanation\": \"...\", \"hint\": \"...\"}\n"
                "task = Ukrainian sentence. answer = correct English translation.\n"
                "explanation in Ukrainian. hint — short tip if stuck."
            )
        elif kind == "grammar":
            user = (
                f"Generate ONE grammar multiple-choice challenge for CEFR {self.level}.\n"
                "Return JSON: {\"task\": \"...\", \"answer\": \"...\", \"explanation\": \"...\", \"hint\": \"...\"}\n"
                "task = question with 4 options marked A/B/C/D. answer = correct letter."
            )
        elif kind == "rephrase":
            user = (
                f"Generate ONE sentence rephrase challenge for CEFR {self.level}.\n"
                "Give an informal sentence; ask learner to rewrite it formally (or vice versa).\n"
                "Return JSON: {\"task\": \"...\", \"answer\": \"...\", \"explanation\": \"...\", \"hint\": \"...\"}"
            )
        else:  # vocab_fill
            user = (
                f"Generate ONE fill-in-the-gap vocabulary challenge for CEFR {self.level}.\n"
                "Return JSON: {\"task\": \"...\", \"answer\": \"...\", \"explanation\": \"...\", \"hint\": \"...\"}\n"
                "task = English sentence with ___ . answer = missing word."
            )

        raw = self.grok.chat_simple(system, user)
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise ValueError("Grok не повернув JSON для daily challenge.")
        data = json.loads(m.group())
        challenge = DailyChallenge(
            date=today,
            kind=kind,
            task=data["task"],
            answer=data["answer"],
            explanation=data["explanation"],
            hint=data.get("hint", ""),
        )
        log_data["history"].append({
            "date": today,
            "kind": kind,
            "task": challenge.task,
            "answer": challenge.answer,
            "explanation": challenge.explanation,
            "hint": challenge.hint,
            "completed": False,
        })
        self._save_log(log_data)
        return challenge

    def check(self, challenge: DailyChallenge, user_answer: str) -> tuple[bool, str]:
        # спрощена перевірка: case-insensitive, strip punctuation
        correct = challenge.answer.strip().lower()
        attempt = user_answer.strip().lower()
        is_correct = correct == attempt or attempt in correct or correct in attempt
        if is_correct:
            self._update_streak(completed=True)
            # позначити як виконане в історії
            log_data = self._load_log()
            for entry in log_data.get("history", []):
                if entry.get("date") == challenge.date:
                    entry["completed"] = True
            self._save_log(log_data)
        return is_correct, challenge.explanation

    # ---- stats ---------------------------------------------------------- #
    def stats(self) -> dict:
        log_data = self._load_log()
        history = log_data.get("history", [])
        completed = [h for h in history if h.get("completed")]
        return {
            "streak": log_data.get("streak", 0),
            "total_challenges": len(history),
            "completed": len(completed),
            "completion_rate": round(100 * len(completed) / len(history), 1) if history else 0,
            "last_date": log_data.get("last_date"),
        }
