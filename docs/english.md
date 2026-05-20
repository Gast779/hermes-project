# English Bot

## Методика

Для україномовного учня (24 роки, рівень припустимо B1 — налаштовується в профілі) бот поєднує чотири доведено-ефективних підходи:

1. **Communicative approach** — будь-яка вправа закінчується питанням, щоб учень формував свою відповідь, а не лише пасивно споживав.
2. **Spaced repetition** — `LessonPlanner` тримає список пройдених граматичних і лексичних тем і ротує їх.
3. **Grammar in context** — кожне граматичне явище подається через приклади, а не як суха таблиця.
4. **L1 leverage** — пояснення українською, приклади англійською (мозок не витрачає сили на парсинг метакомунікації).

## CEFR-syllabus у коді

`lesson_planner.py` містить мапу `GRAMMAR_SYLLABUS`:

- **A1** → to be, Present Simple, articles, plurals, possessives.
- **A2** → Present Continuous, Past Simple, going to/will, compar/super.
- **B1** → Present Perfect, Past Continuous, First conditional, modal verbs, relative clauses.
- **B2** → Present Perfect Continuous, Past Perfect, 2nd/3rd conditional, passive, reported speech, modals of deduction.
- **C1** → Mixed conditionals, inversion, cleft, subjunctive, advanced phrasal verbs, discourse markers.

Лексичні теми (`VOCAB_TOPICS`): daily routines, food, travel, work, technology, **cryptocurrency & trading**, feelings, health, news, entertainment.

## Як використовувати Grok

`grok_client.py` — тонкий wrapper над OpenAI-сумісним endpoint xAI (`https://api.x.ai/v1`).  Моделі:

- `grok-4-0709` — флагман, для уроків і фідбеку (за замовчуванням).
- `grok-2-vision-1212` — для зображень.

Промпти в `prompts.py` дають один зрозумілий output-format на кожну задачу:

| Функція | Промпт |
|---------|--------|
| Vocabulary lesson | `vocab_prompt(topic, level, n_words)` |
| Grammar lesson | `grammar_prompt(topic, level)` |
| Speaking feedback | `speaking_feedback_prompt(transcript, level)` |
| Image description | `image_description_prompt(level)` |
| Translation check | `translation_check_prompt(uk_text, en_attempt, level)` |

## Голосові повідомлення

Grok сам STT не робить. Потрібен окремий transcription-крок. Рекомендую:

1. **OpenAI Whisper API** (`whisper-1`) — найкраща точність, $0.006/min.
2. **faster-whisper** локально — безкоштовно, але потребує GPU чи деякого часу на CPU.

Псевдо-інтеграція:

```python
import whisper                # або faster_whisper
model = whisper.load_model("base")
result = model.transcribe("voice.ogg", language="en")
feedback = bot.feedback_on_speech(result["text"])
```

## Профіль і прогрес

`LessonPlanner` зберігає у `~/.hermes/english_profile.json`:

```json
{
  "level": "B1",
  "completed_grammar": ["Present Simple", "Past Simple"],
  "completed_vocab": ["daily routines"],
  "last_lesson_date": "2026-05-20",
  "streak_days": 7
}
```

Streak оновлюється автоматично при кожному `start_lesson()`.

## Команди

```bash
python main.py english chat                # REPL-чат у терміналі
python main.py english lesson auto         # авто-вибір типу уроку
python main.py english lesson grammar      # граматика
python main.py english lesson vocab        # словник
python main.py english lesson speak        # roleplay
```

## Roadmap

- [ ] Підключити Whisper для голосу.
- [ ] Конвертер у TTS (відповіді бота → mp3, через ElevenLabs або OpenAI TTS).
- [ ] Spaced-repetition engine для лексики (SM-2 / FSRS).
- [ ] Інтеграція з Anki: експорт нових слів у .apkg.
- [ ] Web/Telegram-інтерфейс замість CLI.
