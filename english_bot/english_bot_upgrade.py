"""
Hermes v2.0 — English Bot Upgrade Module
========================================

Покращений модуль вивчення англійської мови з:
- CEFR adaptive framework (A1 -> C2)
- Ukrainian translation protocol (EN -> UK)
- SRS (Spaced Repetition System) на базі SM-2
- Personalized feedback loop
- Comprehensible Input (Krashen i+1)

Адресат: english_bot агент
Telegram: Thread #24 (English Learning)
"""

import sqlite3
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import random
import math


# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent.parent
KB_PATH = PROJECT_ROOT / "hermes_knowledge_base.db"
ENGLISH_DB = PROJECT_ROOT / "english_learning.db"

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# SM-2 Algorithm Constants
SM2_EASE_FACTOR_DEFAULT = 2.5
SM2_INTERVAL_INIT = 1  # days
SM2_EASE_MIN = 1.3
SM2_EASE_MAX = 2.5

# Adaptive difficulty thresholds
DIFFICULTY_UP_THRESHOLD = 0.85   # >85% correct -> level up
DIFFICULTY_DOWN_THRESHOLD = 0.60  # <60% correct -> level down


# ═══════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════

class CEFRLevel(Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class AnswerQuality(Enum):
    AGAIN = 0   # Не знав
    HARD = 3    # Знав з труднощами
    GOOD = 4    # Знав добре
    EASY = 5    # Знав легко


@dataclass
class Flashcard:
    id: int
    word_en: str
    word_uk: str  # український переклад
    example_sentence_en: str
    example_sentence_uk: str
    cefr_level: str
    topic: str
    # SM-2 fields
    ease_factor: float = SM2_EASE_FACTOR_DEFAULT
    interval_days: int = 1
    repetitions: int = 0
    due_date: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(days=1))
    last_reviewed: Optional[datetime] = None


@dataclass
class UserProgress:
    user_id: str
    current_cefr: str = "B1"  # Default
    total_words_learned: int = 0
    total_words_this_week: int = 0
    streak_days: int = 0
    last_study_date: Optional[datetime] = None
    grammar_mastery: Dict[str, float] = field(default_factory=dict)  # topic -> 0-1
    weekly_accuracy: List[float] = field(default_factory=list)  # last 7 sessions
    time_spent_minutes: Dict[str, int] = field(default_factory=dict)  # activity -> minutes


@dataclass
class Lesson:
    lesson_id: str
    cefr_level: str
    topic: str
    components: List[Dict]  # grammar, vocab, listening, speaking, review
    estimated_duration_min: int
    created_at: datetime


@dataclass
class ErrorPattern:
    error_type: str  # grammar, vocabulary, pronunciation, spelling
    specific_error: str
    frequency: int
    example_wrong: str
    example_correct: str
    targeted_exercise: str


# ═══════════════════════════════════════════════════════════════════
# SQLite Database for English Learning
# ═══════════════════════════════════════════════════════════════════

class EnglishDatabase:
    """База даних для відстеження прогресу вивчення англійської."""

    def __init__(self, db_path: Path = ENGLISH_DB):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """Ініціалізація таблиць."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_en TEXT NOT NULL,
                word_uk TEXT NOT NULL,
                example_sentence_en TEXT,
                example_sentence_uk TEXT,
                cefr_level TEXT NOT NULL,
                topic TEXT,
                ease_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 1,
                repetitions INTEGER DEFAULT 0,
                due_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_reviewed TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_progress (
                user_id TEXT PRIMARY KEY,
                current_cefr TEXT DEFAULT 'B1',
                total_words_learned INTEGER DEFAULT 0,
                streak_days INTEGER DEFAULT 0,
                last_study_date TIMESTAMP,
                grammar_mastery TEXT,  -- JSON
                weekly_accuracy TEXT,  -- JSON array
                time_spent TEXT,  -- JSON
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS review_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cards_reviewed INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                avg_quality REAL,
                duration_minutes INTEGER,
                cefr_level TEXT
            );

            CREATE TABLE IF NOT EXISTS error_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                error_type TEXT NOT NULL,
                specific_error TEXT,
                frequency INTEGER DEFAULT 1,
                example_wrong TEXT,
                example_correct TEXT,
                targeted_exercise TEXT,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id TEXT UNIQUE NOT NULL,
                cefr_level TEXT NOT NULL,
                topic TEXT,
                components TEXT,  -- JSON
                estimated_duration_min INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_flashcards_due ON flashcards(due_date);
            CREATE INDEX IF NOT EXISTS idx_flashcards_cefr ON flashcards(cefr_level);
            CREATE INDEX IF NOT EXISTS idx_errors_user ON error_patterns(user_id, error_type);
        """)
        self.conn.commit()

    def add_flashcard(self, word_en: str, word_uk: str, example_en: str, example_uk: str,
                      cefr_level: str, topic: str = "") -> int:
        """Додати нову флеш-картку."""
        cursor = self.conn.execute("""
            INSERT INTO flashcards (word_en, word_uk, example_sentence_en, example_sentence_uk, cefr_level, topic)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (word_en, word_uk, example_en, example_uk, cefr_level, topic))
        self.conn.commit()
        return cursor.lastrowid

    def get_due_cards(self, user_cefr: str, limit: int = 20) -> List[Flashcard]:
        """Отримати картки, які потрібно повторити сьогодні."""
        cursor = self.conn.execute("""
            SELECT * FROM flashcards
            WHERE cefr_level = ? AND due_date <= datetime('now')
            ORDER BY due_date ASC, repetitions ASC
            LIMIT ?
        """, (user_cefr, limit))

        cards = []
        for row in cursor.fetchall():
            cards.append(Flashcard(
                id=row["id"],
                word_en=row["word_en"],
                word_uk=row["word_uk"],
                example_sentence_en=row["example_sentence_en"],
                example_sentence_uk=row["example_sentence_uk"],
                cefr_level=row["cefr_level"],
                topic=row["topic"],
                ease_factor=row["ease_factor"],
                interval_days=row["interval_days"],
                repetitions=row["repetitions"],
                due_date=datetime.fromisoformat(row["due_date"]),
                last_reviewed=datetime.fromisoformat(row["last_reviewed"]) if row["last_reviewed"] else None,
            ))
        return cards

    def update_card_after_review(self, card_id: int, quality: AnswerQuality):
        """Оновити картку після review за SM-2 алгоритмом."""
        cursor = self.conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,))
        row = cursor.fetchone()
        if not row:
            return

        ease = row["ease_factor"]
        interval = row["interval_days"]
        reps = row["repetitions"]
        q = quality.value

        # SM-2 Algorithm
        if q < 3:
            # Again - reset
            reps = 0
            interval = 1
        else:
            # Update ease factor
            ease = ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
            ease = max(SM2_EASE_MIN, min(SM2_EASE_MAX, ease))

            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = int(interval * ease)

            reps += 1

        due = datetime.utcnow() + timedelta(days=interval)

        self.conn.execute("""
            UPDATE flashcards
            SET ease_factor = ?, interval_days = ?, repetitions = ?,
                due_date = ?, last_reviewed = datetime('now')
            WHERE id = ?
        """, (ease, interval, reps, due.isoformat(), card_id))
        self.conn.commit()

    def record_error(self, user_id: str, error_type: str, specific_error: str,
                     example_wrong: str, example_correct: str):
        """Записати помилку користувача."""
        # Перевірити чи вже є така помилка
        cursor = self.conn.execute("""
            SELECT id, frequency FROM error_patterns
            WHERE user_id = ? AND error_type = ? AND specific_error = ?
        """, (user_id, error_type, specific_error))

        existing = cursor.fetchone()
        if existing:
            self.conn.execute("""
                UPDATE error_patterns
                SET frequency = frequency + 1, last_seen = datetime('now')
                WHERE id = ?
            """, (existing["id"],))
        else:
            self.conn.execute("""
                INSERT INTO error_patterns (user_id, error_type, specific_error,
                    example_wrong, example_correct)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, error_type, specific_error, example_wrong, example_correct))

        self.conn.commit()

    def get_common_errors(self, user_id: str, limit: int = 5) -> List[ErrorPattern]:
        """Отримати найчастіші помилки користувача для цільових вправ."""
        cursor = self.conn.execute("""
            SELECT * FROM error_patterns
            WHERE user_id = ?
            ORDER BY frequency DESC
            LIMIT ?
        """, (user_id, limit))

        errors = []
        for row in cursor.fetchall():
            errors.append(ErrorPattern(
                error_type=row["error_type"],
                specific_error=row["specific_error"],
                frequency=row["frequency"],
                example_wrong=row["example_wrong"],
                example_correct=row["example_correct"],
                targeted_exercise=row["targeted_exercise"],
            ))
        return errors

    def get_user_progress(self, user_id: str) -> UserProgress:
        """Отримати прогрес користувача."""
        cursor = self.conn.execute(
            "SELECT * FROM user_progress WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()

        if not row:
            # Create default
            self.conn.execute("""
                INSERT INTO user_progress (user_id) VALUES (?)
            """, (user_id,))
            self.conn.commit()
            return UserProgress(user_id=user_id)

        return UserProgress(
            user_id=row["user_id"],
            current_cefr=row["current_cefr"],
            total_words_learned=row["total_words_learned"],
            streak_days=row["streak_days"],
            last_study_date=datetime.fromisoformat(row["last_study_date"]) if row["last_study_date"] else None,
            grammar_mastery=json.loads(row["grammar_mastery"]) if row["grammar_mastery"] else {},
            weekly_accuracy=json.loads(row["weekly_accuracy"]) if row["weekly_accuracy"] else [],
            time_spent_minutes=json.loads(row["time_spent"]) if row["time_spent"] else {},
        )

    def update_user_progress(self, progress: UserProgress):
        """Оновити прогрес користувача."""
        self.conn.execute("""
            INSERT OR REPLACE INTO user_progress
            (user_id, current_cefr, total_words_learned, streak_days,
             last_study_date, grammar_mastery, weekly_accuracy, time_spent, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            progress.user_id,
            progress.current_cefr,
            progress.total_words_learned,
            progress.streak_days,
            progress.last_study_date.isoformat() if progress.last_study_date else None,
            json.dumps(progress.grammar_mastery),
            json.dumps(progress.weekly_accuracy),
            json.dumps(progress.time_spent_minutes),
        ))
        self.conn.commit()

    def record_session(self, user_id: str, cards_reviewed: int, correct: int,
                       avg_quality: float, duration_min: int, cefr: str):
        """Записати review session."""
        self.conn.execute("""
            INSERT INTO review_sessions
            (user_id, cards_reviewed, correct_answers, avg_quality, duration_minutes, cefr_level)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, cards_reviewed, correct, avg_quality, duration_min, cefr))
        self.conn.commit()

    def close(self):
        self.conn.close()


# ═══════════════════════════════════════════════════════════════════
# SRS Engine (Spaced Repetition System)
# ═══════════════════════════════════════════════════════════════════

class SRSEngine:
    """Движок інтервальних повторень на базі SM-2."""

    def __init__(self, db: EnglishDatabase):
        self.db = db

    def get_next_session_cards(self, user_id: str, max_cards: int = 20) -> List[Flashcard]:
        """Отримати картки для наступної сесії повторення."""
        progress = self.db.get_user_progress(user_id)
        due_cards = self.db.get_due_cards(progress.current_cefr, limit=max_cards)

        # Якщо мало due cards - додати нові
        if len(due_cards) < max_cards // 2:
            new_cards = self._get_new_cards(progress.current_cefr, max_cards - len(due_cards))
            due_cards.extend(new_cards)

        return due_cards[:max_cards]

    def _get_new_cards(self, cefr_level: str, limit: int) -> List[Flashcard]:
        """Отримати нові картки для вивчення."""
        cursor = self.db.conn.execute("""
            SELECT * FROM flashcards
            WHERE cefr_level = ? AND repetitions = 0
            ORDER BY RANDOM()
            LIMIT ?
        """, (cefr_level, limit))

        cards = []
        for row in cursor.fetchall():
            cards.append(Flashcard(
                id=row["id"],
                word_en=row["word_en"],
                word_uk=row["word_uk"],
                example_sentence_en=row["example_sentence_en"],
                example_sentence_uk=row["example_sentence_uk"],
                cefr_level=row["cefr_level"],
                topic=row["topic"],
                ease_factor=row["ease_factor"],
                interval_days=row["interval_days"],
                repetitions=row["repetitions"],
                due_date=datetime.fromisoformat(row["due_date"]),
            ))
        return cards

    def process_answer(self, card_id: int, quality: AnswerQuality):
        """Обробити відповідь користувача."""
        self.db.update_card_after_review(card_id, quality)

    def calculate_retention_rate(self, user_id: str, days: int = 7) -> float:
        """Розрахувати відсоток запам'ятовування."""
        cursor = self.db.conn.execute("""
            SELECT AVG(
                CAST(correct_answers AS FLOAT) / NULLIF(cards_reviewed, 0)
            ) as retention
            FROM review_sessions
            WHERE user_id = ? AND session_date >= datetime('now', ?)
        """, (user_id, f"-{days} days"))

        row = cursor.fetchone()
        return row["retention"] if row and row["retention"] else 0.0


# ═══════════════════════════════════════════════════════════════════
# Adaptive Difficulty Engine
# ═══════════════════════════════════════════════════════════════════

class AdaptiveEngine:
    """Адаптивний двигун масштабування складності."""

    def __init__(self, db: EnglishDatabase):
        self.db = db

    def should_level_up(self, user_id: str) -> bool:
        """Чи варто підвищити CEFR рівень?"""
        progress = self.db.get_user_progress(user_id)

        if not progress.weekly_accuracy:
            return False

        avg_accuracy = sum(progress.weekly_accuracy) / len(progress.weekly_accuracy)
        return avg_accuracy >= DIFFICULTY_UP_THRESHOLD

    def should_level_down(self, user_id: str) -> bool:
        """Чи варто знизити CEFR рівень?"""
        progress = self.db.get_user_progress(user_id)

        if not progress.weekly_accuracy:
            return False

        avg_accuracy = sum(progress.weekly_accuracy) / len(progress.weekly_accuracy)
        return avg_accuracy <= DIFFICULTY_DOWN_THRESHOLD

    def adjust_level(self, user_id: str) -> Tuple[str, str]:
        """Коригувати рівень користувача. Повертає (old_level, new_level)."""
        progress = self.db.get_user_progress(user_id)
        old_level = progress.current_cefr

        if self.should_level_up(user_id):
            idx = CEFR_LEVELS.index(old_level)
            new_level = CEFR_LEVELS[min(idx + 1, len(CEFR_LEVELS) - 1)]
        elif self.should_level_down(user_id):
            idx = CEFR_LEVELS.index(old_level)
            new_level = CEFR_LEVELS[max(idx - 1, 0)]
        else:
            new_level = old_level

        if new_level != old_level:
            progress.current_cefr = new_level
            self.db.update_user_progress(progress)

        return old_level, new_level

    def get_lesson_difficulty(self, user_id: str) -> Dict:
        """Отримати рекомендовану складність уроку."""
        progress = self.db.get_user_progress(user_id)

        # Interleaved practice: чергування типів завдань
        components = {
            "grammar": 0.20,
            "vocabulary": 0.30,
            "listening": 0.20,
            "speaking": 0.20,
            "review": 0.10,
        }

        # Адаптація на основі слабких місць
        errors = self.db.get_common_errors(user_id, limit=3)
        for error in errors:
            if error.error_type == "grammar":
                components["grammar"] += 0.10
            elif error.error_type == "vocabulary":
                components["vocabulary"] += 0.10

        # Нормалізація
        total = sum(components.values())
        components = {k: v/total for k, v in components.items()}

        return {
            "cefr_level": progress.current_cefr,
            "components": components,
            "target_errors": errors,
        }


# ═══════════════════════════════════════════════════════════════════
# Ukrainian Translation Protocol
# ═══════════════════════════════════════════════════════════════════

class UkrainianTranslator:
    """Протокол перекладу EN -> UK для всіх повідомлень."""

    @staticmethod
    def format_bilingual(en_text: str, uk_text: str) -> str:
        """Форматувати повідомлення з обома мовами."""
        return f"""{en_text}

---
[UKRAINSKYI PEREVLAD]
{uk_text}"""

    @staticmethod
    def translate_lesson_content(lesson: Lesson) -> Dict:
        """Перекласти контент уроку."""
        # TODO: інтеграція з Grok API для реального перекладу
        return {
            "instructions_en": f"Today's lesson: {lesson.topic} ({lesson.cefr_level})",
            "instructions_uk": f"Сьогоднішній урок: {lesson.topic} ({lesson.cefr_level})",
            "components": lesson.components,
        }

    @staticmethod
    def translate_flashcard(card: Flashcard) -> Dict:
        """Перекласти флеш-картку."""
        return {
            "front_en": card.word_en,
            "front_uk": card.word_uk,
            "back_en": card.example_sentence_en,
            "back_uk": card.example_sentence_uk,
        }


# ═══════════════════════════════════════════════════════════════════
# Lesson Generator
# ═══════════════════════════════════════════════════════════════════

class LessonGenerator:
    """Генератор уроків на основі CEFR та прогресу."""

    def __init__(self, db: EnglishDatabase, adaptive: AdaptiveEngine):
        self.db = db
        self.adaptive = adaptive

    def generate_daily_lesson(self, user_id: str) -> Dict:
        """Згенерувати щоденний урок."""
        difficulty = self.adaptive.get_lesson_difficulty(user_id)
        cefr = difficulty["cefr_level"]

        lesson = {
            "cefr_level": cefr,
            "topic": self._select_topic(user_id),
            "duration_min": 30,
            "components": [],
        }

        # Grammar component (20%)
        lesson["components"].append({
            "type": "grammar",
            "duration_min": 6,
            "content": f"Grammar exercise for {cefr} level",
        })

        # Vocabulary component (30%)
        srs = SRSEngine(self.db)
        cards = srs.get_next_session_cards(user_id, max_cards=10)
        lesson["components"].append({
            "type": "vocabulary",
            "duration_min": 9,
            "flashcards": [UkrainianTranslator.translate_flashcard(c) for c in cards],
        })

        # Listening component (20%)
        lesson["components"].append({
            "type": "listening",
            "duration_min": 6,
            "content": "Listen and comprehend exercise",
        })

        # Speaking component (20%)
        lesson["components"].append({
            "type": "speaking",
            "duration_min": 6,
            "content": "Roleplay or pronunciation practice",
        })

        # Review component (10%)
        lesson["components"].append({
            "type": "review",
            "duration_min": 3,
            "content": "SRS review of previous material",
        })

        return lesson

    def _select_topic(self, user_id: str) -> str:
        """Вибрати тему уроку на основі інтересів/помилок."""
        errors = self.db.get_common_errors(user_id, limit=1)
        if errors:
            return f"Focus: {errors[0].error_type} correction"
        topics = ["Daily Life", "Work", "Travel", "Technology", "Health", "Finance"]
        return random.choice(topics)


# ═══════════════════════════════════════════════════════════════════
# Progress Dashboard
# ═══════════════════════════════════════════════════════════════════

class ProgressDashboard:
    """Дашборд прогресу вивчення англійської."""

    def __init__(self, db: EnglishDatabase):
        self.db = db

    def get_dashboard(self, user_id: str) -> Dict:
        """Отримати повний дашборд прогресу."""
        progress = self.db.get_user_progress(user_id)
        srs = SRSEngine(self.db)
        retention = srs.calculate_retention_rate(user_id)

        # Stats
        cursor = self.db.conn.execute("""
            SELECT COUNT(*) as total_cards,
                   SUM(CASE WHEN repetitions > 0 THEN 1 ELSE 0 END) as learned,
                   SUM(CASE WHEN due_date <= datetime('now') THEN 1 ELSE 0 END) as due
            FROM flashcards
            WHERE cefr_level = ?
        """, (progress.current_cefr,))

        stats = cursor.fetchone()

        # Recent sessions
        cursor = self.db.conn.execute("""
            SELECT * FROM review_sessions
            WHERE user_id = ?
            ORDER BY session_date DESC
            LIMIT 7
        """, (user_id,))
        recent_sessions = [dict(row) for row in cursor.fetchall()]

        # Common errors
        errors = self.db.get_common_errors(user_id, limit=5)

        return {
            "cefr_level": progress.current_cefr,
            "total_words_learned": progress.total_words_learned,
            "streak_days": progress.streak_days,
            "retention_rate": f"{retention*100:.1f}%",
            "cards_total": stats["total_cards"],
            "cards_learned": stats["learned"],
            "cards_due": stats["due"],
            "recent_sessions": recent_sessions,
            "common_errors": [
                {
                    "type": e.error_type,
                    "error": e.specific_error,
                    "frequency": e.frequency,
                    "example_wrong": e.example_wrong,
                    "example_correct": e.example_correct,
                }
                for e in errors
            ],
            "time_distribution": progress.time_spent_minutes,
        }

    def format_dashboard_message(self, dashboard: Dict) -> str:
        """Форматувати дашборд для Telegram (EN + UK)."""
        en = f"""📊 Your English Progress Dashboard

CEFR Level: {dashboard['cefr_level']}
Words Learned: {dashboard['total_words_learned']}
Current Streak: {dashboard['streak_days']} days
Retention Rate: {dashboard['retention_rate']}
Cards Due Today: {dashboard['cards_due']}

Common Errors to Fix:
"""
        for i, e in enumerate(dashboard['common_errors'][:3], 1):
            en += f"{i}. {e['type']}: {e['error']} ({e['frequency']}x)\n"

        uk = f"""📊 Ваш прогрес вивчення англійської

Рівень CEFR: {dashboard['cefr_level']}
Вивчено слів: {dashboard['total_words_learned']}
Поточна серія: {dashboard['streak_days']} днів
Відсоток запам'ятовування: {dashboard['retention_rate']}
Карток на сьогодні: {dashboard['cards_due']}

Поширені помилки для виправлення:
"""
        for i, e in enumerate(dashboard['common_errors'][:3], 1):
            uk += f"{i}. {e['type']}: {e['error']} ({e['frequency']} разів)\n"

        return UkrainianTranslator.format_bilingual(en, uk)


# ═══════════════════════════════════════════════════════════════════
# Main Interface
# ═══════════════════════════════════════════════════════════════════

class EnglishTutor:
    """Головний інтерфейс English Bot."""

    def __init__(self):
        self.db = EnglishDatabase()
        self.srs = SRSEngine(self.db)
        self.adaptive = AdaptiveEngine(self.db)
        self.lesson_gen = LessonGenerator(self.db, self.adaptive)
        self.dashboard = ProgressDashboard(self.db)
        self.translator = UkrainianTranslator()

    def daily_lesson(self, user_id: str) -> str:
        """Щоденний урок (EN + UK)."""
        lesson = self.lesson_gen.generate_daily_lesson(user_id)

        en = f"""📚 Daily Lesson — {lesson['topic']} ({lesson['cefr_level']})

Today's plan ({lesson['duration_min']} min):
"""
        uk = f"""📚 Щоденний урок — {lesson['topic']} ({lesson['cefr_level']})

План на сьогодні ({lesson['duration_min']} хв):
"""

        for comp in lesson['components']:
            emoji = {"grammar": "📝", "vocabulary": "📖", "listening": "🎧",
                     "speaking": "🗣️", "review": "🔄"}.get(comp['type'], "•")
            en += f"{emoji} {comp['type'].title()}: {comp['duration_min']} min\n"
            uk += f"{emoji} {comp['type'].title()}: {comp['duration_min']} хв\n"

        return self.translator.format_bilingual(en, uk)

    def review_session(self, user_id: str, max_cards: int = 20) -> str:
        """Сесія повторення (SRS)."""
        cards = self.srs.get_next_session_cards(user_id, max_cards)

        if not cards:
            en = "🎉 No cards due for review! Great job!"
            uk = "🎉 Немає карток для повторення! Чудова робота!"
            return self.translator.format_bilingual(en, uk)

        en = f"📝 SRS Review Session — {len(cards)} cards due\n\n"
        uk = f"📝 Сесія повторення SRS — {len(cards)} карток на сьогодні\n\n"

        for card in cards:
            en += f"Q: {card.word_en}\n   {card.example_sentence_en}\n\n"
            uk += f"П: {card.word_uk}\n   {card.example_sentence_uk}\n\n"

        return self.translator.format_bilingual(en, uk)

    def grammar_exercise(self, user_id: str) -> str:
        """Граматична вправа на основі помилок."""
        errors = self.db.get_common_errors(user_id, limit=1)

        if not errors:
            en = "📝 Grammar Practice\n\nNo recurring errors found! Let's practice conditionals."
            uk = "📝 Граматична вправа\n\nПомилок не знайдено! Потренуємо умовні речення."
            return self.translator.format_bilingual(en, uk)

        error = errors[0]
        en = f"""📝 Targeted Grammar Exercise

Focus: {error.error_type} — {error.specific_error}
Example correction:
❌ {error.example_wrong}
✅ {error.example_correct}

Practice this pattern with 5 sentences."""

        uk = f"""📝 Цільова граматична вправа

Фокус: {error.error_type} — {error.specific_error}
Приклад виправлення:
❌ {error.example_wrong}
✅ {error.example_correct}

Потренуйте цей паттерн у 5 реченнях."""

        return self.translator.format_bilingual(en, uk)

    def pronunciation_feedback(self, user_id: str, transcribed_text: str,
                               expected_text: str) -> str:
        """Зворотній зв'язок по вимові (через Whisper)."""
        # Simple comparison - could be enhanced with phonetic analysis
        similarity = self._text_similarity(transcribed_text, expected_text)

        if similarity > 0.9:
            en = f"🎯 Excellent pronunciation! ({similarity*100:.0f}% match)"
            uk = f"🎯 Чудова вимова! ({similarity*100:.0f}% збіг)"
        elif similarity > 0.7:
            en = f"👍 Good try! ({similarity*100:.0f}% match) — Focus on word stress."
            uk = f"👍 Хороша спроба! ({similarity*100:.0f}% збіг) — Зверніть увагу на наголос."
        else:
            en = f"💪 Keep practicing! ({similarity*100:.0f}% match) — Listen and repeat slowly."
            uk = f"💪 Продовжуйте практикуватися! ({similarity*100:.0f}% збіг) — Слухайте та повторюйте повільно."

        return self.translator.format_bilingual(en, uk)

    def _text_similarity(self, a: str, b: str) -> float:
        """Просте порівняння текстів (можна замінити на більш складне)."""
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        if not a_words or not b_words:
            return 0.0
        intersection = a_words & b_words
        return len(intersection) / max(len(a_words), len(b_words))

    def progress_report(self, user_id: str) -> str:
        """Звіт про прогрес (EN + UK)."""
        dashboard = self.dashboard.get_dashboard(user_id)
        return self.dashboard.format_dashboard_message(dashboard)

    def streak_check(self, user_id: str) -> str:
        """Перевірити та оновити streak."""
        progress = self.db.get_user_progress(user_id)

        today = datetime.utcnow().date()
        last = progress.last_study_date.date() if progress.last_study_date else None

        if last == today:
            return None  # Already studied today

        if last and (today - last).days == 1:
            progress.streak_days += 1
        else:
            progress.streak_days = 1  # Reset or start new

        progress.last_study_date = datetime.utcnow()
        self.db.update_user_progress(progress)

        en = f"🔥 Streak: {progress.streak_days} days! Keep it up!"
        uk = f"🔥 Серія: {progress.streak_days} днів! Продовжуйте!"
        return self.translator.format_bilingual(en, uk)

    def close(self):
        self.db.close()


# ═══════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tutor = EnglishTutor()

    # Demo
    user_id = "demo_user"

    print("=" * 60)
    print(tutor.daily_lesson(user_id))
    print("=" * 60)
    print(tutor.progress_report(user_id))
    print("=" * 60)
    print(tutor.grammar_exercise(user_id))
