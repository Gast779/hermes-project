"""
English Learning Bot
====================

Персональний тренер англійської для україномовного користувача (CEFR A1..C2).

Архітектура:
    - grok_client.py   — OpenAI-compatible клієнт до xAI Grok.
    - lesson_planner.py — генерує план уроку: тип вправ, теми, граматичні фокуси.
    - prompts.py       — каталог промптів для різних задач (vocab/grammar/speaking).
    - handlers.py      — обробка text / image / voice.

Підхід:
    - Communicative + spaced repetition + grammar-in-context.
    - Пояснення українською, приклади — англійською.
    - Кожен урок ≤ 10 хв.  Прогрес зберігається у JSON.
"""

from .flashcards import Flashcard, FlashcardDeck, RATING_LABELS
from .grok_client import GrokClient
from .lesson_planner import LessonPlanner, Lesson, LessonType
from .handlers import EnglishBot
from .progress import ProgressDashboard
from .daily import DailyChallenge, DailyEngine
from .podcast import PodcastEngine, PodcastScript, PodcastLevel
from .quizzes import QuizEngine, QuizKind, QuizSession

__all__ = ["GrokClient", "LessonPlanner", "Lesson", "LessonType", "EnglishBot", 
           "FlashcardDeck", "Flashcard", "RATING_LABELS",
           "QuizEngine", "QuizKind", "QuizSession",
           "PodcastEngine", "PodcastScript", "PodcastLevel",
           "DailyEngine", "DailyChallenge",
           "ProgressDashboard"]
