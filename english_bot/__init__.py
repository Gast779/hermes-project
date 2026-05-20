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

from .grok_client import GrokClient
from .lesson_planner import LessonPlanner, Lesson, LessonType
from .handlers import EnglishBot

__all__ = ["GrokClient", "LessonPlanner", "Lesson", "LessonType", "EnglishBot"]
