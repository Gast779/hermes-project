"""
Високорівневий API бота.

Один клас `EnglishBot` поєднує: Grok-клієнт + LessonPlanner + промпти.
Видає готові відповіді на 4 типи вводу: lesson, text-msg, image, voice-transcript.
"""
from __future__ import annotations

import logging

from . import prompts
from .grok_client import GrokClient
from .lesson_planner import Lesson, LessonPlanner, LessonType

log = logging.getLogger(__name__)


class EnglishBot:
    def __init__(
        self,
        grok: GrokClient,
        planner: LessonPlanner | None = None,
        transcriber=None,                # lazy: підключиш коли треба голос
    ):
        self.grok = grok
        self.planner = planner or LessonPlanner()
        self.transcriber = transcriber

    def handle_voice(self, audio_bytes: bytes, *, language: str = "en",
                     level: str | None = None) -> dict:
        """
        Голос → транскрипт → фідбек.
        Повертає {"transcript": "...", "feedback": "..."}.
        """
        if self.transcriber is None:
            raise RuntimeError(
                "Transcriber not configured. "
                "Pass `Transcriber(backend='openai')` to EnglishBot constructor."
            )
        # для faster-whisper параметр називається інакше — обережно
        self.transcriber.language = language
        transcript = self.transcriber.transcribe(audio_bytes)
        if not transcript:
            return {"transcript": "", "feedback": "Не вдалося розпізнати мову на записі."}
        feedback = self.feedback_on_speech(transcript, level=level)
        return {"transcript": transcript, "feedback": feedback}

    # --------------- lesson flow ---------------
    def start_lesson(self, lesson_type: LessonType | None = None) -> tuple[Lesson, str]:
        lesson = self.planner.plan(prefer=lesson_type)
        system = prompts.SYSTEM_TUTOR.format(level=lesson.level)
        if lesson.type == LessonType.GRAMMAR:
            user = prompts.grammar_prompt(lesson.topic, lesson.level)
        elif lesson.type == LessonType.VOCABULARY:
            user = prompts.vocab_prompt(lesson.topic, lesson.level)
        elif lesson.type == LessonType.SPEAKING:
            user = (
                f"Start a short roleplay (≤ 5 turns) for scenario: {lesson.topic}. "
                "You start with one short line in English, then wait for me to reply."
            )
        else:
            user = f"Lead a short {lesson.type.value} lesson on: {lesson.topic}."
        text = self.grok.chat_simple(system, user)
        return lesson, text

    def complete_lesson(self, lesson: Lesson) -> None:
        self.planner.mark_completed(lesson)

    # --------------- ad-hoc text ---------------
    def reply_text(self, user_message: str, *, level: str | None = None) -> str:
        lvl = level or self.planner.profile.level
        system = prompts.SYSTEM_TUTOR.format(level=lvl)
        return self.grok.chat_simple(system, user_message)

    def check_translation(self, uk: str, en_attempt: str, *, level: str | None = None) -> str:
        lvl = level or self.planner.profile.level
        return self.grok.chat_simple(
            prompts.SYSTEM_TUTOR.format(level=lvl),
            prompts.translation_check_prompt(uk, en_attempt, lvl),
        )

    # --------------- image ---------------
    def reply_image(self, image_bytes: bytes, mime: str = "image/jpeg",
                    extra_question: str = "", level: str | None = None) -> str:
        lvl = level or self.planner.profile.level
        system = prompts.SYSTEM_TUTOR.format(level=lvl)
        user_text = prompts.image_description_prompt(lvl)
        if extra_question:
            user_text += f"\n\nThe learner also asks: {extra_question}"
        return self.grok.chat_with_image(system, user_text, image_bytes, image_mime=mime)

    # --------------- voice ---------------
    def feedback_on_speech(self, transcript: str, *, level: str | None = None) -> str:
        """
        Беремо вже-розпізнаний текст і даємо фідбек.
        Сама транскрипція — поза цим класом (Whisper / faster-whisper).
        """
        lvl = level or self.planner.profile.level
        return self.grok.chat_simple(
            prompts.SYSTEM_TUTOR.format(level=lvl),
            prompts.speaking_feedback_prompt(transcript, lvl),
        )
