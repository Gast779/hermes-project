"""
Каталог промптів для English Bot.

Принципи:
    1. Пояснення граматики — *українською*.
    2. Приклади і завдання — *англійською*.
    3. Завжди один чіткий output format, щоб легко парсити в боті.
"""
from __future__ import annotations

SYSTEM_TUTOR = """\
You are a friendly, patient English tutor for a Ukrainian speaker (CEFR level: {level}).
Rules:
- Explain grammar concepts in UKRAINIAN.
- Give example sentences and exercises in ENGLISH.
- Be concise. Avoid corporate filler.
- When the learner makes a mistake, point it out gently and show the correct version.
- Always end with one short follow-up question to keep the conversation going.
"""


def vocab_prompt(topic: str, level: str, n_words: int = 7) -> str:
    return f"""\
Generate a vocabulary mini-lesson on the topic: "{topic}". Level: {level}.

Format:
1. Word list ({n_words} items). For each:
   - English word/phrase
   - IPA transcription
   - Ukrainian translation
   - One example sentence in English

2. Quick exercise: 3 gap-fill sentences using these words. List answers separately at the end.

Keep total length ≤ 350 words.
"""


def grammar_prompt(topic: str, level: str) -> str:
    return f"""\
Lesson topic: {topic}. Level: {level}.

Structure your reply as:
1. ПОЯСНЕННЯ (Ukrainian, 4–6 sentences): when is this used, what it contrasts with.
2. FORM (table or formula in English).
3. EXAMPLES (5 English sentences, with Ukrainian translations).
4. EXERCISE: 5 questions where the learner must transform / fill the gap.
5. ANSWERS (hidden behind a heading "✅ Відповіді").
"""


def speaking_feedback_prompt(transcript: str, level: str) -> str:
    return f"""\
The learner (CEFR {level}) said the following sentence(s) in English:

"{transcript}"

Do all of this in your reply:
1. Identify grammar/lexical/pronunciation mistakes (if any).
2. Give a corrected version.
3. Explain the FIRST mistake in Ukrainian (1–3 sentences).
4. Suggest 2 more natural / native alternative phrasings.
5. Ask one follow-up question in English to continue practice.
"""


def image_description_prompt(level: str) -> str:
    return f"""\
You are an English tutor (learner level: {level}).
The learner sent an image. Do this:
1. Describe what is in the image in simple English (≤ 4 sentences).
2. Pull out 5 vocabulary items from your description; for each show:
   English word — IPA — Ukrainian translation.
3. Ask 3 questions in English about the image to spark a conversation.
"""


def translation_check_prompt(uk_text: str, en_attempt: str, level: str) -> str:
    return f"""\
Учень рівня {level} переклав з української на англійську.

Українське речення:
"{uk_text}"

Спроба учня:
"{en_attempt}"

1. Знайди помилки (граматичні, лексичні, природність).
2. Дай 2 правильні варіанти перекладу (формальний і нейтральний).
3. Поясни найголовнішу помилку українською (≤ 3 речень).
"""
