"""
Hermes — головна CLI-точка входу.

Команди:
    python main.py polymarket scan                       # одноразовий пошук арбітражу
    python main.py polymarket monitor "trump"            # моніторинг ринків за темою
    python main.py polymarket realtime --tokens 0x... 0x...
    python main.py polymarket cross                      # крос-маркет з Kalshi
    python main.py polymarket depth-scan                 # глибокий арбітраж
    python main.py polymarket news                       # новини + ринки
    python main.py crypto report                         # одноразовий звіт
    python main.py crypto watch                          # daemon: fast movers
    python main.py english lesson [grammar|vocab|speak]  # генерація уроку
    python main.py english chat                          # інтерактивний REPL
    python main.py scheduler                             # повний розклад (7 skills)
    
RooFlow:
    python main.py rooflow status                        # dashboard всіх агентів
    python main.py rooflow mode <agent> <mode>           # перемикання режиму
    python main.py rooflow memory <agent> <file>         # читання Memory Bank
    python main.py rooflow handoff <from> <to> <task>    # створення handoff
    python main.py rooflow predict <market> <prob>      # новий прогноз
    python main.py rooflow resolve <PR-id> <true/false>  # закрити прогноз
    python main.py rooflow predictions [--status active]   # реєстр прогнозів
    python main.py rooflow prediction-stats               # статистика Brier
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from config import env, settings, setup_logging
from crypto_monitor import (
    BinanceClient,
    CoinGeckoClient,
    FastMoversWatcher,
    build_scheduler,
    generate_daily_report,
)
from crypto_monitor.scheduler import add_cron_job
from english_bot import (
    DailyEngine,
    EnglishBot,
    FlashcardDeck,
    GrokClient,
    LessonPlanner,
    LessonType,
    PodcastEngine,
    ProgressDashboard,
    QuizEngine,
    RATING_LABELS,
)
from polymarket_analyzer import (
    InternalArbitrageFinder,
    PolymarketClient,
    TopicMonitor,
    format_arbitrage_report,
    format_topic_report,
)
from polymarket_analyzer.cross_market import CrossMarketAnalyzer, KalshiClient
from polymarket_analyzer.realtime import PolymarketRealtime
from polymarket_analyzer.reporter import format_cross_market_report
from scripts.notify_telegram import send_telegram
from rooflow.engine import RooFlowEngine, MODE_DESCRIPTIONS
from rooflow.scheduler import rooflow_wrap, build_rooflow_scheduler
from rooflow.skills_sync import sync_skills, sync_single_skill

setup_logging()
log = logging.getLogger("hermes")
console = Console()

app = typer.Typer(no_args_is_help=True, help="Hermes Multi-Agent System")
poly = typer.Typer(help="Polymarket аналітика")
crypto = typer.Typer(help="Криптовалютні звіти та алерти")
english = typer.Typer(help="Тренер англійської")
rooflow = typer.Typer(help="RooFlow multi-agent orchestration")
app.add_typer(poly, name="polymarket")
app.add_typer(crypto, name="crypto")
app.add_typer(english, name="english")
app.add_typer(rooflow, name="rooflow")


# =========================================================================== #
# POLYMARKET
# =========================================================================== #
@poly.command("scan")
def polymarket_scan(
    max_markets: int = typer.Option(300, help="Скільки топ-ринків сканувати"),
    min_edge: float = typer.Option(0.01, help="Мін. edge для сигналу (1% = 0.01)"),
    min_volume: float = typer.Option(1000.0, help="Мін. 24h volume у USDC"),
    notify: bool = typer.Option(False, help="Надіслати у Telegram"),
) -> None:
    """Одноразовий пошук внутрішнього арбітражу в Polymarket."""
    with PolymarketClient() as client:
        finder = InternalArbitrageFinder(
            client, min_edge=min_edge, min_volume_usd=min_volume
        )
        opps = finder.find(max_markets=max_markets)
    report = format_arbitrage_report(opps)
    console.print(Markdown(report))
    if notify and opps:
        send_telegram(report)


@poly.command("monitor")
def polymarket_monitor(
    keyword: str = typer.Argument(..., help="Ключове слово, наприклад 'trump'"),
    interval: int = typer.Option(30, help="Інтервал поллінгу, сек"),
    once: bool = typer.Option(False, help="Зробити один тік і вийти"),
    notify: bool = typer.Option(False, help="Telegram-нотифікації"),
) -> None:
    """Моніторинг ринків Polymarket за обраною темою."""
    with PolymarketClient() as client:
        mon = TopicMonitor(client, keyword)

        def _emit(report) -> None:
            text = format_topic_report(report)
            console.print(Markdown(text))
            if notify and (report.arbitrage or report.significant_changes):
                send_telegram(text)

        if once:
            _emit(mon.tick())
        else:
            mon.watch(poll_interval_seconds=interval, on_change=_emit)


@poly.command("cross")
def polymarket_cross(
    keyword: str = typer.Option("", help="Опційний фільтр по темі"),
    max_markets: int = typer.Option(200),
) -> None:
    """Порівняти Polymarket з Kalshi (через fuzzy-match питань)."""
    with PolymarketClient() as pm:
        kalshi = KalshiClient()
        try:
            analyzer = CrossMarketAnalyzer(pm, [kalshi])
            discrep = analyzer.find_discrepancies(keyword=keyword or None, max_markets=max_markets)
        finally:
            kalshi.close()
    console.print(Markdown(format_cross_market_report(discrep)))


@poly.command("realtime")
def polymarket_realtime(
    tokens: list[str] = typer.Option(..., "--tokens", "-t", help="token_id-и для підписки"),
) -> None:
    """WebSocket-стрім CLOB для перелічених token_id."""
    async def _on_change(token_id: str, bid: float, ask: float, msg: dict) -> None:
        console.print(f"[bold cyan]{token_id[:10]}…[/] bid={bid:.4f} ask={ask:.4f}")

    rt = PolymarketRealtime(token_ids=tokens, callback=_on_change)
    try:
        asyncio.run(rt.run())
    except KeyboardInterrupt:
        log.info("WS stopped.")


@poly.command("news")
def polymarket_news(
    min_score: float = typer.Option(0.25, help="Мін. score збігу новина↔ринок"),
    max_markets: int = typer.Option(300),
) -> None:
    """Звʼязати новини з RSS-фідів із ринками Polymarket."""
    from polymarket_analyzer.news_linker import NewsLinker, format_news_links

    with PolymarketClient() as client:
        linker = NewsLinker(client, min_score=min_score, max_markets=max_markets)
        try:
            matches = linker.link()
        finally:
            linker.close()
    console.print(Markdown(format_news_links(matches)))


@poly.command("depth-scan")
def polymarket_depth_scan(
    max_markets: int = typer.Option(100),
    min_edge: float = typer.Option(0.005, help="Мін. edge per share після slippage"),
    min_capital: float = typer.Option(50.0, help="Мін. реальний капітал, USDC"),
    max_slippage_bps: float = typer.Option(200.0, help="Макс. slippage у basis points"),
) -> None:
    """
    Глибокий пошук арбітражу з урахуванням повного orderbook (slippage-aware).
    Повільніший за `scan`, але показує реальні розміри й прибутки.
    """
    from polymarket_analyzer.depth_arbitrage import DepthArbitrageFinder

    results = []
    with PolymarketClient() as client:
        markets = client.fetch_markets(active=True, max_total=max_markets)
        finder = DepthArbitrageFinder(
            client,
            min_edge_per_share=min_edge,
            min_capital_usdc=min_capital,
            max_slippage_bps=max_slippage_bps,
        )
        for i, m in enumerate(markets, 1):
            log.info("[%s/%s] depth-analyze %s", i, len(markets), m.slug)
            r = finder.analyze(m)
            if r:
                results.append(r)

    results.sort(key=lambda r: r.expected_profit_usdc, reverse=True)
    if not results:
        console.print("[yellow]Жодних реалістичних арбітражних можливостей не знайдено.[/]")
        return

    table = Table(title=f"Deep Arbitrage — {len(results)} opportunities")
    table.add_column("Edge/share")
    table.add_column("Capital")
    table.add_column("Profit")
    table.add_column("Kind")
    table.add_column("Market")
    for r in results[:20]:
        table.add_row(
            f"{r.edge_per_share:+.3%}",
            f"${r.max_capital_usdc:,.0f}",
            f"[green]${r.expected_profit_usdc:,.2f}[/]",
            r.kind,
            r.question[:55] + ("…" if len(r.question) > 55 else ""),
        )
    console.print(table)


# =========================================================================== #
# CRYPTO
# =========================================================================== #
def _make_cg() -> CoinGeckoClient:
    cfg = settings()["crypto_monitor"]["data_source"]
    return CoinGeckoClient(api_key=env("COINGECKO_API_KEY"), base_url=cfg["coingecko_base"])


@crypto.command("report")
def crypto_report(notify: bool = typer.Option(False, help="Надіслати у Telegram")) -> None:
    """Згенерувати звіт по крипті прямо зараз."""
    cg = _make_cg()
    try:
        tz = settings()["general"]["timezone"]
        top_n = settings()["crypto_monitor"]["top_n_for_report"]
        report = generate_daily_report(cg, timezone=tz, top_n=top_n)
    finally:
        cg.close()
    console.print(Markdown(report))
    if notify:
        send_telegram(report)


def crypto_report_job() -> None:
    """Hermes-skill entrypoint: завжди шле у Telegram."""
    cg = _make_cg()
    try:
        tz = settings()["general"]["timezone"]
        top_n = settings()["crypto_monitor"]["top_n_for_report"]
        report = generate_daily_report(cg, timezone=tz, top_n=top_n)
    finally:
        cg.close()
    send_telegram(report)


def _alert_callback(alert) -> None:
    cfg = settings()["notifications"]["formats"]
    text = cfg["crypto_alert"].format(
        symbol=alert.symbol,
        pct=alert.pct_change,
        window=alert.window,
        price=alert.price,
        url=alert.chart_url,
    )
    console.print(f"[bold red]ALERT[/] {text}")
    send_telegram(
        text,
        chat_id="-1003792129186",
        message_thread_id=26,
    )


@crypto.command("watch")
def crypto_watch(
    interval: int = typer.Option(60, "--interval", "-i", help="Poll interval in seconds"),
    threshold_5m: float = typer.Option(5.0, "--threshold", "-t", help="Alert threshold % for 5m window"),
) -> None:
    """Daemon: моніторинг fast-movers (Ctrl-C — стоп)."""
    crypto_watch_loop(interval=interval, threshold_5m=threshold_5m)


@crypto.command("whale-alert")
def crypto_whale_alert() -> None:
    """🐋 Сканувати та показати whale transactions."""
    from crypto_monitor.whale_alerts import scan_and_alert
    
    console.print("[bold green]🐋 Whale Alert Scan...[/]")
    alerts = scan_and_alert()
    
    if not alerts:
        console.print("[yellow]Немає significant whale moves за останній період.[/]")
        return
    
    console.print(f"[bold green]Знайдено {len(alerts)} whale transaction(s):[/]\n")
    for alert in alerts:
        console.print(alert)
        console.print("─" * 50)


def crypto_watch_loop(interval: int | None = None, threshold_5m: float | None = None) -> None:
    cfg = settings()["crypto_monitor"]["alerts"]
    cg = _make_cg()
    watcher = FastMoversWatcher(
        cg,
        callback=_alert_callback,
        pct_5m=threshold_5m if threshold_5m is not None else cfg["thresholds"]["pct_5m"],
        pct_1h=cfg["thresholds"]["pct_1h"],
        poll_interval_seconds=interval if interval is not None else cfg["poll_interval_seconds"],
        min_volume_24h=cfg["min_volume_usd_24h"],
        min_market_cap=cfg["min_market_cap_usd"],
        cooldown_minutes=cfg["cooldown_minutes"],
    )
    try:
        watcher.run_forever()
    finally:
        cg.close()


# =========================================================================== #
# ENGLISH
# =========================================================================== #
def _make_bot() -> EnglishBot:
    model = settings()["english_bot"]["grok_model"]
    grok = GrokClient(model=model)  # api_key береться з .env автоматично
    return EnglishBot(grok, LessonPlanner())


@english.command("lesson")
def english_lesson(
    kind: str = typer.Argument("auto", help="auto | grammar | vocab | speak"),
) -> None:
    """Згенерувати один урок."""
    type_map = {
        "auto": None,
        "grammar": LessonType.GRAMMAR,
        "vocab": LessonType.VOCABULARY,
        "speak": LessonType.SPEAKING,
    }
    if kind not in type_map:
        raise typer.BadParameter(f"Unknown kind: {kind}")
    bot = _make_bot()
    lesson, text = bot.start_lesson(type_map[kind])
    console.rule(f"[bold green]{lesson.type.value.upper()} — {lesson.topic}")
    console.print(Markdown(text))
    if typer.confirm("Урок виконано?", default=True):
        bot.complete_lesson(lesson)
        console.print("[green]Збережено в профіль.[/]")


@english.command("chat")
def english_chat() -> None:
    """Інтерактивний чат-тьютор у терміналі."""
    bot = _make_bot()
    console.print("[bold green]English tutor.[/] Натисни Ctrl-C для виходу. Введи 'lesson' для уроку.")
    while True:
        try:
            user = console.input("[bold]you>[/] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\nGoodbye!")
            break
        if not user:
            continue
        if user.lower() == "lesson":
            lesson, text = bot.start_lesson()
            console.print(Markdown(text))
            continue
        try:
            reply = bot.reply_text(user)
        except Exception as e:        # noqa: BLE001
            log.exception("Grok call failed: %s", e)
            console.print(f"[red]Error:[/] {e}")
            continue
        console.print(Markdown(reply))


@english.command("voice")
def english_voice(
    audio_file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
    backend: str = typer.Option("openai", help="openai | faster-whisper"),
    language: str = typer.Option("en", help="en | uk | auto"),
) -> None:
    """Аналіз голосового файлу: транскрипція + фідбек на вимову."""
    from english_bot.transcriber import Transcriber
    bot = _make_bot()
    bot.transcriber = Transcriber(backend=backend, language=None if language == "auto" else language)

    with open(audio_file, "rb") as fh:
        audio_bytes = fh.read()
    result = bot.handle_voice(audio_bytes, language=language)

    console.rule("[cyan]Transcript")
    console.print(result["transcript"])
    console.rule("[green]Feedback")
    console.print(Markdown(result["feedback"]))


@english.command("word")
def english_word(
    word: str = typer.Argument(..., help="Українське або англійське слово/фраза"),
    level: str = typer.Option("B1", help="CEFR рівень (A1..C1)"),
    tag: str = typer.Option("", help="Тег через кому, напр. 'work,crypto'"),
) -> None:
    """Додати слово в колоду (Grok заповнить переклад, IPA, приклад)."""
    from english_bot.prompts import SYSTEM_TUTOR
    grok = GrokClient()
    prompt = (
        f"Add flashcard for: \"{word}\". Level: {level}.\n\n"
        "Return ONLY valid JSON with these fields:\n"
        "  front (string) — українське слово/фраза\n"
        "  back (string) — англійське слово/фраза\n"
        "  ipa (string) — IPA транскрипція\n"
        "  example (string) — приклад речення англійською (≤ 12 слів)\n"
        "  example_uk (string) — переклад речення українською\n"
        "No markdown, no comments."
    )
    system = SYSTEM_TUTOR.format(level=level)
    raw = grok.chat_simple(system, prompt)
    # Парсинг JSON з відповіді (Grok може обгорнути у markdown)
    import re
    import json as _json
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        console.print(f"[red]Grok не повернув JSON:\n{raw}[/]")
        raise typer.Exit(1)
    try:
        data = _json.loads(m.group())
    except _json.JSONDecodeError as e:
        console.print(f"[red]Помилка парсингу JSON: {e}\n{raw}[/]")
        raise typer.Exit(1)

    deck = FlashcardDeck()
    card = deck.add(
        front=data.get("front", word),
        back=data.get("back", ""),
        ipa=data.get("ipa", ""),
        example=data.get("example", ""),
        example_uk=data.get("example_uk", ""),
        level=level,
        tags=[t.strip() for t in tag.split(",") if t.strip()],
    )
    console.print(f"[green]✅ Додано картку[/] [bold]{card.front}[/] → {card.back} {card.ipa}")
    console.print(f"   Приклад: {card.example}")


@english.command("flashcard")
def english_flashcard(
    count: int = typer.Option(10, help="Скільки карток повторити"),
) -> None:
    """SRS-повторення флеш-карток."""
    deck = FlashcardDeck()
    due = deck.due_cards()
    if not due:
        console.print("[yellow]На сьогодні немає карток для повторення.[/]")
        console.print(f"[dim]Всього в колоді: {deck.stats()['total']}[/]")
        return

    console.print(f"[bold green]📚 Карток на сьогодні: {len(due)}[/] (показую max {count})")
    for card in due[:count]:
        console.rule(f"[bold]{card.front}[/]  [dim]({card.ipa})[/]")
        _ = console.input("[dim]Натисни Enter для відповіді...[/]")
        console.print(f"[bold green]{card.back}[/]")
        if card.example:
            console.print(f"[dim]Приклад:[/] {card.example}")
        console.print()
        # Вибір рейтингу
        for k, v in RATING_LABELS.items():
            console.print(f"  [{k}] {v}")
        choice = console.input("[bold]Оцінка (0-3):[/] ").strip()
        try:
            rating = int(choice)
            if rating not in (0, 1, 2, 3):
                raise ValueError
        except ValueError:
            console.print("[yellow]Некоректний ввід — встановлено 'hard' (1).[/]")
            rating = 1
        deck.review(card.id, rating)
        console.print(f"   [dim]Наступне повторення: {card.due_date}[/]\n")

    console.print("[green]Готово! Картки оновлено.[/]")


@english.command("deck")
def english_deck() -> None:
    """Переглянути статистику колоди."""
    deck = FlashcardDeck()
    st = deck.stats()
    table = Table(title="📚 Flashcard Deck")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Всього карток", str(st["total"]))
    table.add_row("На сьогодні", str(st["due_today"]))
    table.add_row("  └ Нові", str(st["new"]))
    table.add_row("  └ Повторення", str(st["review"]))
    table.add_row("Вивчено (≥3 reps)", str(st["mature"]))
    console.print(table)

    # Міні-таблиця карток на сьогодні
    due = deck.due_cards()[:20]
    if due:
        console.print("\n[bold]Сьогоднішні картки:[/]")
        t2 = Table()
        t2.add_column("🇺🇦")
        t2.add_column("🇬🇧")
        t2.add_column("Interval")
        t2.add_column("Reps")
        for c in due:
            t2.add_row(c.front, c.back, f"{c.interval}d", str(c.repetitions))
        console.print(t2)


@english.command("telegram-test")
def english_telegram_test(
    lesson_type: str = typer.Option("grammar", help="grammar | vocab | speaking"),
) -> None:
    """📨 Manual override: надіслати урок в Telegram thread 24 (тест delivery)."""
    from english_bot import GrokClient, LessonPlanner, EnglishBot
    from english_bot.lesson_planner import LessonType
    
    console.print(f"[bold green]📨 Тест Telegram delivery для {lesson_type}...[/]")
    
    model = settings()["english_bot"]["grok_model"]
    grok = GrokClient(model=model)
    bot = EnglishBot(grok, LessonPlanner())
    
    lt = LessonType(lesson_type) if lesson_type in ["grammar", "vocab", "speaking"] else LessonType.GRAMMAR
    lesson, text = bot.start_lesson(lesson_type=lt)
    
    header = f"🇬🇧 **English Lesson — {lesson.type.value.upper()}**\n\n"
    full_text = header + text
    
    # Відправити
    send_telegram(
        full_text,
        chat_id="-1003792129186",
        message_thread_id=_get_topic("english"),
    )
    
    console.print(f"[bold green]✅ Урок надіслано в Telegram thread 24[/]")
    console.print(f"[dim]Тип: {lesson.type.value} | Тема: {lesson.topic}[/]")
    console.print(f"[dim]Розмір: {len(full_text)} chars[/]")


@english.command("quiz")
def english_quiz(
    kind: str = typer.Argument("mixed", help="grammar | vocab | mixed"),
    count: int = typer.Option(5, help="Кількість питань"),
    level: str = typer.Option("B1", help="CEFR рівень"),
) -> None:
    """🧠 Інтерактивний квіз — grammar, vocab або mixed."""
    if kind not in ("grammar", "vocab", "mixed"):
        raise typer.BadParameter(f"Unknown kind: {kind}")
    grok = GrokClient()
    engine = QuizEngine(grok, level=level)
    session = engine.start(kind=kind, count=count)  # type: ignore[arg-type]

    console.print(f"[bold green]🧠 {kind.upper()} Quiz — {len(session.questions)} questions[/]\n")
    for q in session.questions:
        console.rule(f"Question {q.id}")
        console.print(f"[bold]{q.question}[/]\n")
        for i, opt in enumerate(q.options, start=1):
            letter = chr(64 + i)  # A, B, C, D
            console.print(f"   {letter}. {opt}")
        choice_raw = console.input("Відповідь (A-D): ").strip().upper()
        choice_map = {"A": 0, "B": 1, "C": 2, "D": 3}
        choice_idx = choice_map.get(choice_raw, -1)
        correct, explanation = engine.record_answer(session, q.id, choice_idx)
        if correct:
            console.print(f"[green]✅ Правильно![/]\n")
        else:
            correct_letter = chr(65 + q.correct_index)
            console.print(f"[red]❌ Ні. Правильна: {correct_letter}. {q.options[q.correct_index]}[/]")
        console.print(f"[dim]💡 {explanation}[/]\n")

    result = engine.finish(session)
    console.rule(f"[bold]Результат: {result['correct']}/{result['total']} ({result['score_pct']}%)[/]")


@english.command("podcast")
def english_podcast(
    topic: str = typer.Option("", help="Тема діалогу (порожньо = випадкова)"),
    level: str = typer.Option("B1", help="CEFR рівень"),
) -> None:
    """🎧 Listening practice — діалог + comprehension questions."""
    grok = GrokClient()
    engine = PodcastEngine(grok, level=level)
    script = engine.generate(topic=topic or None)
    engine.save_to_history(script)

    console.rule(f"[bold magenta]🎧 {script.title}[/]  [dim]({script.level})[/]")
    console.print(f"[dim]Topic:[/] {script.topic}\n")

    # Діалог
    for turn in script.dialog:
        speaker_color = "cyan" if turn["speaker"] == "Alex" else "green"
        console.print(f"[{speaker_color}]{turn['speaker']}:[/] {turn['text']}")
    console.print()

    # Словник
    if script.vocabulary:
        console.rule("[bold]📖 Key Vocabulary[/]")
        for item in script.vocabulary:
            console.print(f"  • [bold]{item['word']}[/] {item.get('ipa', '')} — {item['uk']}")
        console.print()

    # Comprehension questions
    if script.questions:
        correct_count = 0
        for i, q in enumerate(script.questions, 1):
            console.print(f"[bold]{i}. {q['question']}[/]")
            for j, opt in enumerate(q["options"], start=1):
                console.print(f"   {j}. {opt}")
            choice = console.input("Відповідь (1-4): ").strip()
            try:
                idx = int(choice) - 1
                if idx == q["correct"]:
                    console.print("[green]✅ Правильно![/]\n")
                    correct_count += 1
                else:
                    console.print(f"[red]❌ Ні. Правильна: {q['correct'] + 1}. {q['options'][q['correct']]}[/]\n")
            except (ValueError, IndexError):
                console.print(f"[yellow]⚠ Некоректно. Правильна: {q['correct'] + 1}.[/]\n")

        pct = round(100 * correct_count / len(script.questions), 1)
        console.rule(f"[bold]Результат: {correct_count}/{len(script.questions)} ({pct}%)[/]")


@english.command("daily")
def english_daily(
    level: str = typer.Option("B1", help="CEFR рівень"),
) -> None:
    """📅 Щоденний челлендж: переклад, граматика, rephrase або fill-in-gap."""
    grok = GrokClient()
    engine = DailyEngine(grok, level=level)

    # Показати streak
    streak_info = engine.streak()
    if streak_info["status"] == "done":
        console.print(f"[green]✅ Сьогоднішній челлендж вже виконано! Streak: {streak_info['streak']} 🔥[/]")
        return
    elif streak_info["status"] == "broken":
        console.print(f"[yellow]⚠ Streak зірвано. Починаємо заново![/]")
    else:
        console.print(f"[dim]🔥 Поточний streak: {streak_info['streak']}[/]")

    challenge = engine.generate()
    console.rule(f"[bold cyan]📅 Daily Challenge — {challenge.date}[/]  [dim]({challenge.kind})[/]")
    console.print(f"\n[bold]{challenge.task}[/]\n")
    if challenge.hint:
        console.print(f"[dim]💡 Підказка: {challenge.hint}[/]\n")

    answer = console.input("[bold]Твоя відповідь:[/] ").strip()
    is_correct, explanation = engine.check(challenge, answer)

    if is_correct:
        console.print(f"\n[green]✅ Правильно![/]")
        console.print(f"[green]🔥 Streak: {engine.streak()['streak']} днів[/]")
    else:
        console.print(f"\n[red]❌ Ні. Правильна відповідь:[/] {challenge.answer}")
    console.print(f"[dim]Пояснення: {explanation}[/]")


@english.command("stats")
def english_stats() -> None:
    """📊 Прогрес-дашборд: уроки, картки, квізи, streak, слабкі місця."""
    dash = ProgressDashboard()
    data = dash.build()

    console.rule(f"[bold green]📊 English Progress — Level {data['level']}[/]")

    # Уроки
    t1 = Table(title="Lessons")
    t1.add_column("Metric")
    t1.add_column("Value")
    t1.add_row("Пройдено тем", str(data["lessons"]["completed"]))
    t1.add_row("Streak (уроки)", f"{data['lessons']['streak']} 🔥")
    console.print(t1)

    # Флеш-карти
    t2 = Table(title="Flashcards")
    t2.add_column("Metric")
    t2.add_column("Value")
    t2.add_row("Всього карток", str(data["flashcards"]["total"]))
    t2.add_row("Вивчено (≥3 reps)", str(data["flashcards"]["mature"]))
    t2.add_row("На сьогодні", str(data["flashcards"]["due_today"]))
    console.print(t2)

    # Квізи
    t3 = Table(title="Quizzes")
    t3.add_column("Metric")
    t3.add_column("Value")
    t3.add_row("Сесій", str(data["quizzes"]["total_sessions"]))
    t3.add_row("Середній бал", f"{data['quizzes']['avg_score']}%")
    if data["quizzes"]["grammar_accuracy"] is not None:
        t3.add_row("Grammar accuracy", f"{data['quizzes']['grammar_accuracy']}%")
    if data["quizzes"]["vocab_accuracy"] is not None:
        t3.add_row("Vocab accuracy", f"{data['quizzes']['vocab_accuracy']}%")
    console.print(t3)

    # Daily
    t4 = Table(title="Daily Challenges")
    t4.add_column("Metric")
    t4.add_column("Value")
    t4.add_row("Всього", str(data["daily"]["total"]))
    t4.add_row("Виконано", str(data["daily"]["completed"]))
    t4.add_row("Відсоток", f"{data['daily']['completion_rate']}%")
    t4.add_row("Streak", f"{data['daily']['streak']} 🔥")
    console.print(t4)

    # Podcasts
    t5 = Table(title="Podcasts")
    t5.add_column("Metric")
    t5.add_column("Value")
    t5.add_row("Прослухано", str(data["podcasts"]["total"]))
    console.print(t5)

    # Слабкі місця
    if data["weak_spots"]:
        console.print("\n[bold red]⚠ Слабкі місця:[/]")
        for spot in data["weak_spots"]:
            console.print(f"  • {spot}")


# =========================================================================== #
# ROOFLOW
# =========================================================================== #
@rooflow.command("status")
def rooflow_status() -> None:
    """📊 RooFlow dashboard — статус всіх агентів."""
    engine = RooFlowEngine()
    data = engine.dashboard()

    console.rule("[bold magenta]🎭 RooFlow Multi-Agent Dashboard[/]")
    
    # Статус агентів
    for agent, info in data["agents"].items():
        mode_icon = {"architect": "🏗️", "code": "💻", "debug": "🐛", "ask": "❓", "orchestrate": "🎭"}.get(info["mode"], "❓")
        console.print(f"\n[bold]{agent}[/]  {mode_icon} {info['mode']}")
        if info["task"]:
            console.print(f"   [dim]Завдання:[/] {info['task']}")
        console.print(f"   [dim]Перемикань режимів:[/] {info['history_count']}")
        console.print(f"   [dim]Оновлено:[/] {info['last_updated'][:19]}")

    # Active handoffs
    handoffs_content = engine.read_shared("handoffs.md")
    active_count = handoffs_content.count("🔴 active")
    completed_count = handoffs_content.count("🟢 completed")
    if active_count > 0 or completed_count > 0:
        console.print(f"\n[bold]Handoffs:[/] 🔴 {active_count} active | 🟢 {completed_count} completed")
    
    # Skills info (якщо є)
    try:
        from hermes_integration.hermes_adapter import load_skills
        skills = load_skills()
        active_skills = [s for s in skills if s.enabled]
        console.print(f"\n[bold]Skills:[/] {len(active_skills)} active / {len(skills)} total")
    except Exception:
        pass  # skills config не обов'язковий

    if data["shared_files"]:
        console.print(f"\n[bold]Shared Memory:[/] {len(data['shared_files'])} files")
        for fname, fsize in data["shared_files"].items():
            console.print(f"   • {fname} ({fsize} bytes)")


@rooflow.command("mode")
def rooflow_mode(
    agent: str = typer.Argument(..., help="english_bot | crypto_monitor | polymarket_analyzer | mirofish"),
    mode: str = typer.Argument(..., help="architect | code | debug | ask | orchestrate"),
    reason: str = typer.Option("", help="Причина перемикання"),
) -> None:
    """🔄 Перемкнути RooFlow режим для агента."""
    if agent not in ("english_bot", "crypto_monitor", "polymarket_analyzer", "mirofish"):
        raise typer.BadParameter(f"Unknown agent: {agent}")
    if mode not in ("architect", "code", "debug", "ask", "orchestrate"):
        raise typer.BadParameter(f"Unknown mode: {mode}")

    engine = RooFlowEngine()
    result = engine.switch_mode(agent, mode, reason)
    icon = {"architect": "🏗️", "code": "💻", "debug": "🐛", "ask": "❓", "orchestrate": "🎭"}.get(mode, "❓")
    console.print(f"[bold green]{icon} {agent}[/] → {mode}")
    if reason:
        console.print(f"[dim]Причина: {reason}[/]")
    console.print(f"[dim]Попередній: {result['previous']}[/]")


@rooflow.command("memory")
def rooflow_memory(
    agent: str = typer.Argument(..., help="english_bot | crypto_monitor | polymarket_analyzer | mirofish | shared"),
    file: str = typer.Argument(..., help="Файл Memory Bank (напр. activeContext.md)"),
) -> None:
    """📝 Прочитати Memory Bank файл."""
    engine = RooFlowEngine()
    if agent == "shared":
        content = engine.read_shared(file)
    else:
        content = engine.read_memory_bank(agent, file)
    console.rule(f"[bold cyan]{agent}/{file}[/]")
    console.print(Markdown(content))


@rooflow.command("handoff")
def rooflow_handoff(
    from_agent: str = typer.Argument(..., help="Відправник"),
    to_agent: str = typer.Argument(..., help="Отримувач"),
    task: str = typer.Argument(..., help="Опис завдання"),
    deliverables: str = typer.Option("", help="Результати через кому"),
) -> None:
    """📤 Створити handoff між агентами."""
    if from_agent not in ("english_bot", "crypto_monitor", "polymarket_analyzer", "mirofish"):
        raise typer.BadParameter(f"Unknown from_agent: {from_agent}")
    if to_agent not in ("english_bot", "crypto_monitor", "polymarket_analyzer", "mirofish"):
        raise typer.BadParameter(f"Unknown to_agent: {to_agent}")

    engine = RooFlowEngine()
    dels = [d.strip() for d in deliverables.split(",") if d.strip()]
    hid = engine.create_handoff(from_agent, to_agent, task, dels)
    console.print(f"[bold green]📤 Handoff створено:[/] {hid}")
    console.print(f"   [dim]{from_agent} → {to_agent}[/]")
    console.print(f"   [dim]Завдання: {task}[/]")


@rooflow.command("complete")
def rooflow_complete(
    handoff_id: str = typer.Argument(..., help="ID handoff (напр. HO-20260521-123456)"),
    result: str = typer.Argument(..., help="Результат виконання"),
) -> None:
    """✅ Позначити handoff як виконаний."""
    engine = RooFlowEngine()
    engine.complete_handoff(handoff_id, result)
    console.print(f"[bold green]✅ Handoff {handoff_id} виконано[/]")
    console.print(f"   [dim]Результат: {result}[/]")


@rooflow.command("agents")
def rooflow_agents() -> None:
    """📋 Перелік агентів та їх RooFlow режими."""
    console.rule("[bold]🎭 RooFlow Agents[/]")
    for mode, desc in MODE_DESCRIPTIONS.items():
        console.print(f"\n{desc}")
    console.print("\n[dim]Агенти: english_bot, crypto_monitor, polymarket_analyzer, mirofish[/]")


@rooflow.command("sync-skills")
def rooflow_sync_skills() -> None:
    """🔄 Синхронізувати Hermes skills з RooFlow Memory Bank."""
    results = sync_skills()
    console.print("[bold green]🔄 Skills синхронізовано![/]")
    for agent, skill_ids in results.items():
        console.print(f"\n[bold]{agent}:[/]")
        for sid in skill_ids:
            console.print(f"  • {sid}")


@rooflow.command("sync-skill")
def rooflow_sync_single(skill_id: str = typer.Argument(..., help="ID skill для синхронізації")) -> None:
    """🔄 Синхронізувати один skill з RooFlow Memory Bank."""
    success = sync_single_skill(skill_id)
    if success:
        console.print(f"[bold green]✅ Skill {skill_id} синхронізовано[/]")
    else:
        console.print(f"[bold red]❌ Skill {skill_id} не знайдено або не може бути змаплено[/]")


@rooflow.command("execution-log")
def rooflow_execution_log(
    agent: str = typer.Option("", help="Фільтр за агентом (english_bot | crypto_monitor | polymarket_analyzer | mirofish)"),
    lines: int = typer.Option(20, help="Кількість останніх записів"),
) -> None:
    """📋 Переглянути execution log."""
    engine = RooFlowEngine()
    content = engine.read_shared("executionLog.md")
    
    if not content or "## Записи" not in content:
        console.print("[yellow]Execution log порожній.[/]")
        return
    
    # Парсимо записи
    lines_list = content.split("\n")
    entries = [l for l in lines_list if l.strip().startswith("-") and (not agent or f"[{agent}]" in l or f"[{agent.upper()}]" in l)]
    
    console.rule(f"[bold cyan]📋 Execution Log {'— ' + agent if agent else ''}[/]")
    for entry in entries[-lines:]:
        console.print(entry)


@rooflow.command("jobs")
def rooflow_jobs() -> None:
    """📅 Переглянути заплановані cron job'и."""
    try:
        from hermes_integration.hermes_adapter import load_skills
        skills = load_skills()
        
        console.rule("[bold green]📅 Scheduled Jobs[/]")
        table = Table()
        table.add_column("Job Name")
        table.add_column("Agent")
        table.add_column("Schedule")
        table.add_column("Status")
        
        for skill in skills:
            if skill.schedule and skill.schedule != "null":
                agent = "unknown"
                for prefix, a in {"english": "english_bot", "crypto": "crypto_monitor", "polymarket": "polymarket_analyzer", "mirofish": "mirofish"}.items():
                    if prefix in skill.id.lower():
                        agent = a
                        break
                
                sched_str = str(skill.schedule)
                if isinstance(skill.schedule, list):
                    sched_str = "\n".join(skill.schedule)
                
                status = "✅ enabled" if skill.enabled else "⏸️ disabled"
                table.add_row(skill.name, agent, sched_str, status)
        
        console.print(table)
    except Exception as e:
        console.print(f"[yellow]Помилка завантаження jobs: {e}[/]")


@rooflow.command("predictions")
def rooflow_predictions(
    status: str = typer.Option("", help="Фільтр: active | resolved | all"),
) -> None:
    """📊 Переглянути реєстр прогнозів."""
    engine = RooFlowEngine()
    content = engine.read_shared("predictionRegistry.md")
    
    if not content or "## Активні Прогнози" not in content:
        console.print("[yellow]Prediction Registry порожній.[/]")
        return
    
    stats = engine.get_prediction_stats()
    console.rule(f"[bold cyan]📊 Prediction Registry[/]")
    console.print(f"Всього: {stats['total']} | Активні: {stats['active']} | Вирішені: {stats['resolved']}")
    if stats['avg_brier'] is not None:
        console.print(f"Середній Brier: {stats['avg_brier']:.4f}")
    
    # Показати записи
    lines = content.split("\n")
    in_entries = False
    for line in lines:
        if line.startswith("### PR-"):
            in_entries = True
        if in_entries:
            if status == "active" and "🟢 active" not in line and not line.startswith("###"):
                continue
            if status == "resolved" and "⚫ resolved" not in line and not line.startswith("###"):
                continue
            console.print(line)


@rooflow.command("predict")
def rooflow_predict(
    market: str = typer.Argument(..., help="Назва ринку/події"),
    probability: float = typer.Argument(..., help="Ймовірність (0.0-1.0)"),
    bull: float = typer.Option(0.0, help="Bull сценарій"),
    bear: float = typer.Option(0.0, help="Bear сценарій"),
    catalysts: str = typer.Option("", help="Каталізатори через кому"),
) -> None:
    """🎯 Зареєструвати новий прогноз."""
    engine = RooFlowEngine()
    cats = [c.strip() for c in catalysts.split(",") if c.strip()]
    pred_id = engine.register_prediction(
        agent="mirofish",
        market=market,
        probability=probability,
        scenarios={"baseline": probability, "bull": bull, "bear": bear},
        catalysts=cats,
    )
    console.print(f"[bold green]🎯 Прогноз зареєстровано:[/] {pred_id}")
    console.print(f"   Ринок: {market}")
    console.print(f"   Ймовірність: {probability:.1%}")


@rooflow.command("resolve")
def rooflow_resolve(
    prediction_id: str = typer.Argument(..., help="ID прогнозу (PR-YYYYMMDD-HHMMSS)"),
    occurred: bool = typer.Argument(..., help="Чи відбулась подія (true/false)"),
) -> None:
    """✅ Закрити прогноз та обчислити Brier score."""
    engine = RooFlowEngine()
    result = engine.resolve_prediction(prediction_id, occurred)
    
    if "error" in result:
        console.print(f"[bold red]❌ {result['error']}[/]")
        return
    
    console.print(f"[bold green]✅ Прогноз закрито:[/] {prediction_id}")
    console.print(f"   Forecast: {result['forecast']:.1%}")
    console.print(f"   Actual: {result['actual']:.1%}")
    console.print(f"   Brier Score: {result['brier']:.4f} {result['grade']}")


@rooflow.command("prediction-stats")
def rooflow_prediction_stats() -> None:
    """📈 Статистика прогнозів (Brier scores)."""
    engine = RooFlowEngine()
    stats = engine.get_prediction_stats()
    
    console.rule("[bold cyan]📈 Prediction Statistics[/]")
    table = Table()
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Всього прогнозів", str(stats["total"]))
    table.add_row("Активні", str(stats["active"]))
    table.add_row("Вирішені", str(stats["resolved"]))
    if stats["avg_brier"] is not None:
        table.add_row("Середній Brier", f"{stats['avg_brier']:.4f}")
        table.add_row("Найкращий Brier", f"{stats['best_brier']:.4f}")
        table.add_row("Найгірший Brier", f"{stats['worst_brier']:.4f}")
    console.print(table)


@rooflow.command("run-workflow")
def rooflow_run_workflow(
    workflow: str = typer.Argument(..., help="sentiment | prediction | stress-test"),
    arg: str = typer.Option("", help="Аргумент для workflow (напр. market question)"),
) -> None:
    """🔄 Запустити між-агентний workflow."""
    from rooflow.workflows import WorkflowRunner
    
    runner = WorkflowRunner()
    
    if workflow not in runner.workflows:
        console.print(f"[bold red]❌ Невідомий workflow: {workflow}[/]")
        console.print(f"[dim]Доступні: {', '.join(runner.workflows.keys())}[/]")
        raise typer.Exit(1)
    
    console.print(f"[bold green]🚀 Запуск workflow: {workflow}[/]")
    
    if workflow == "sentiment":
        result = runner.run_sentiment_scan(keyword=arg or "bitcoin")
    elif workflow == "prediction":
        if not arg:
            console.print("[yellow]⚠️ Вкажіть market question: --arg \"Will BTC hit 70k?\"[/]")
            raise typer.Exit(1)
        result = runner.run_prediction_packet(market_question=arg)
    elif workflow == "stress-test":
        result = runner.run_stress_test(market=arg or "BTC")
    else:
        result = runner.workflows[workflow]()
    
    console.print(f"[bold green]✅ Workflow завершено:[/] {result['status']}")
    console.print(f"[dim]Handoff: {result.get('handoff_id', 'N/A')}[/]")
    if 'prediction_id' in result:
        console.print(f"[dim]Prediction: {result['prediction_id']}[/]")


@rooflow.command("workflows")
def rooflow_workflows() -> None:
    """📋 Перелік доступних workflow."""
    from rooflow.workflows import WorkflowRunner
    
    runner = WorkflowRunner()
    console.rule("[bold cyan]🔄 Available Workflows[/]")
    
    table = Table()
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Agents")
    table.add_column("Telegram Thread")
    
    for wf in runner.list_workflows():
        table.add_row(
            wf["id"],
            wf["name"],
            " → ".join(wf["agents"]),
            str(wf["telegram"]),
        )
    console.print(table)


@rooflow.command("calibrate")
def rooflow_calibrate() -> None:
    """📊 Запустити щотижневу калібрацію Brier score (manual run)."""
    from rooflow.calibration import run_weekly_calibration
    
    console.print("[bold green]📊 Запуск weekly calibration...[/]")
    result = run_weekly_calibration()
    
    console.print(f"[bold green]✅ Calibration завершено:[/]")
    console.print(f"   Прогнозів: {result['predictions_total']}")
    console.print(f"   Вирішено: {result['resolved']}")
    console.print(f"   Середній Brier: {result['avg_brier']:.4f}" if result['avg_brier'] else "   Немає даних")
    console.print(f"   Expired: {result['expired_count']}")


@rooflow.command("health")
def rooflow_health() -> None:
    """🏥 Перевірити здоров'я всіх scheduler job'ів."""
    from rooflow.health_monitor import HealthMonitor
    
    monitor = HealthMonitor()
    report = monitor.format_health_report()
    
    console.print(report)
    
    # Також відправити в Telegram
    try:
        from scripts.notify_telegram import send_telegram
        send_telegram(
            report,
            chat_id="-1003792129186",
            message_thread_id=25,
        )
        console.print("\n[dim]Health report sent to Telegram thread 25[/]")
    except Exception:
        pass


# =========================================================================== #
# DB / HISTORY
# =========================================================================== #
db_cmd = typer.Typer(help="Перегляд історії в SQLite")
app.add_typer(db_cmd, name="db")


@db_cmd.command("stats")
def db_stats() -> None:
    """Підрахунок записів у БД."""
    from storage import Storage
    with Storage() as s:
        st = s.stats()
    table = Table(title="Storage stats")
    table.add_column("Table")
    table.add_column("Count")
    for k, v in st.items():
        table.add_row(k, str(v))
    console.print(table)


@db_cmd.command("alerts")
def db_alerts(coin: str = typer.Option("", help="фільтр по coin_id"), limit: int = 20) -> None:
    """Останні crypto-алерти."""
    from storage import Storage
    with Storage() as s:
        rows = s.recent_alerts(coin_id=coin or None, limit=limit)
    if not rows:
        console.print("[yellow]Немає записів.[/]")
        return
    table = Table(title=f"Last {len(rows)} alerts")
    for col in ("ts_utc", "symbol", "window", "pct_change", "price_usd"):
        table.add_column(col)
    for r in rows:
        table.add_row(r["ts_utc"][:19], r["symbol"], r["window"],
                      f"{r['pct_change']:+.2f}%", f"${r['price_usd']:.4f}")
    console.print(table)


@db_cmd.command("arb")
def db_arb(limit: int = 20) -> None:
    """Останні знайдені арбітражні можливості."""
    from storage import Storage
    with Storage() as s:
        rows = s.recent_arb(limit=limit)
    if not rows:
        console.print("[yellow]Немає записів.[/]")
        return
    table = Table(title=f"Last {len(rows)} arbitrage opportunities")
    for col in ("ts_utc", "kind", "edge", "volume_usd", "slug"):
        table.add_column(col)
    for r in rows:
        table.add_row(r["ts_utc"][:19], r["kind"], f"{r['edge']:+.3%}",
                      f"${r['volume_usd']:,.0f}", r["slug"][:50])
    console.print(table)



# =========================================================================== #
# SCHEDULED JOBS — 7 Skills (Hermes Admin config)
# =========================================================================== #

# Telegram Topic IDs
def _get_topic(skill_name: str) -> int:
    topics = {
        "english": 24,
        "crypto_report": 25,
        "fast_movers": 26,
        "pm_arb": 27,
        "pm_depth": 28,
        "pm_news": 29,
        "pm_topic": 30,
    }
    return topics.get(skill_name, 24)


def english_daily_job() -> None:
    """🇬🇧 English Daily Lesson → Telegram thread 24."""
    from english_bot import GrokClient, LessonPlanner, EnglishBot
    model = settings()["english_bot"]["grok_model"]
    grok = GrokClient(model=model)
    bot = EnglishBot(grok, LessonPlanner())
    lesson, text = bot.start_lesson()
    
    header = f"🇬🇧 **English Lesson — {lesson.type.value.upper()}**\n\n"
    send_telegram(
        header + text,
        chat_id="-1003792129186",
        message_thread_id=_get_topic("english"),
    )


def crypto_report_job() -> None:
    """💰 Crypto Daily Report → Telegram thread 25."""
    cg = _make_cg()
    try:
        tz = settings()["general"]["timezone"]
        top_n = settings()["crypto_monitor"]["top_n_for_report"]
        report = generate_daily_report(cg, timezone=tz, top_n=top_n)
    finally:
        cg.close()
    send_telegram(
        report,
        chat_id="-1003792129186",
        message_thread_id=_get_topic("crypto_report"),
    )


def fast_movers_job() -> None:
    """🚀 Fast Movers Scan → Telegram thread 26 (one-shot)."""
    import subprocess
    result = subprocess.run(
        ["python", "scripts/fast_movers_scan.py"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent),
    )
    if result.returncode == 1 and result.stdout:  # Були алерти
        send_telegram(
            result.stdout,
            chat_id="-1003792129186",
            message_thread_id=_get_topic("fast_movers"),
        )


def polymarket_scan_job() -> None:
    """🎯 Polymarket Arbitrage Scan → Telegram thread 27."""
    with PolymarketClient() as client:
        cfg = settings()["polymarket"]["arbitrage"]
        finder = InternalArbitrageFinder(
            client, min_edge=cfg["min_edge"], min_volume_usd=cfg["min_volume_usd"]
        )
        opps = finder.find()
    if opps:
        send_telegram(
            format_arbitrage_report(opps),
            chat_id="-1003792129186",
            message_thread_id=_get_topic("pm_arb"),
        )


def polymarket_depth_job() -> None:
    """🔍 Polymarket Deep Scan → Telegram thread 28."""
    from polymarket_analyzer.depth_arbitrage import DepthArbitrageFinder
    
    results = []
    with PolymarketClient() as client:
        markets = client.fetch_markets(active=True, max_total=100)
        finder = DepthArbitrageFinder(
            client,
            min_edge_per_share=0.005,
            min_capital_usdc=50.0,
            max_slippage_bps=200.0,
        )
        for i, m in enumerate(markets, 1):
            log.info("[%s/%s] depth-analyze %s", i, len(markets), m.slug)
            r = finder.analyze(m)
            if r:
                results.append(r)
    
    results.sort(key=lambda r: r.expected_profit_usdc, reverse=True)
    if results:
        lines = [f"🔍 **Deep Arbitrage — {len(results)} opportunities**"]
        for r in results[:20]:
            lines.append(
                f"• {r.question[:50]}…\n"
                f"  Edge: {r.edge_per_share:+.3%} | Capital: ${r.max_capital_usdc:,.0f} | "
                f"Profit: ${r.expected_profit_usdc:,.2f} | {r.kind}"
            )
        send_telegram(
            "\n".join(lines),
            chat_id="-1003792129186",
            message_thread_id=_get_topic("pm_depth"),
        )


def polymarket_news_job() -> None:
    """📰 Polymarket News Linker → Telegram thread 29."""
    from polymarket_analyzer.news_linker import NewsLinker, format_news_links
    
    with PolymarketClient() as client:
        linker = NewsLinker(client, min_score=0.25, max_markets=300)
        try:
            matches = linker.link()
        finally:
            linker.close()
    if matches:
        send_telegram(
            format_news_links(matches),
            chat_id="-1003792129186",
            message_thread_id=_get_topic("pm_news"),
        )


def polymarket_topic_job() -> None:
    """👁️ Polymarket Topic Monitor → Telegram thread 30."""
    with PolymarketClient() as client:
        mon = TopicMonitor(client, "trump")
        report = mon.tick()
    if report.arbitrage or report.significant_changes:
        send_telegram(
            format_topic_report(report),
            chat_id="-1003792129186",
            message_thread_id=_get_topic("pm_topic"),
        )

def weekly_calibration_job() -> None:
    """📊 Weekly Brier Calibration → Telegram thread 30."""
    from rooflow.calibration import run_weekly_calibration
    run_weekly_calibration()


def auto_sentiment_job() -> None:
    """📊 Auto Sentiment Scan → Telegram thread 26 (кожні 6 год)."""
    from rooflow.workflows import WorkflowRunner
    runner = WorkflowRunner()
    runner.run_sentiment_scan(keyword="bitcoin")


def auto_prediction_job() -> None:
    """🎯 Auto Prediction Packet → Telegram thread 27 (кожні 12 год)."""
    from rooflow.workflows import WorkflowRunner
    runner = WorkflowRunner()
    # TODO: Trigger based on market volatility or news volume
    # For now: scheduled scan of top Polymarket markets
    runner.run_prediction_packet(market_question="Top PM market scan", probability=0.5)


def dashboard_job() -> None:
    """🤖 RooFlow Dashboard → Telegram кожні 30 хв."""
    from rooflow.dashboard import send_dashboard
    send_dashboard()


# =========================================================================== #
# SCHEDULER
# =========================================================================== #
@app.command("scheduler")
def run_scheduler() -> None:
    """🚀 Запустити всі 7 Skills за розкладом (blocking)."""
    tz = settings()["general"]["timezone"]
    sched = build_scheduler(timezone=tz)

    # 7 Skills — повний розклад (Hermes Admin config)
    jobs_config = [
        # 🇬🇧 English — 09:00 щодня
        {"job": english_daily_job, "cron": "0 9 * * *", "agent": "english_bot", "mode": "code"},
        
        # 💰 Crypto Reports — 08:00, 14:00, 20:00
        {"job": crypto_report_job, "cron": "0 8 * * *", "agent": "crypto_monitor", "mode": "code"},
        {"job": crypto_report_job, "cron": "0 14 * * *", "agent": "crypto_monitor", "mode": "code"},
        {"job": crypto_report_job, "cron": "0 20 * * *", "agent": "crypto_monitor", "mode": "code"},
        
        # 🚀 Fast Movers — кожні 5 хв
        {"job": fast_movers_job, "cron": "*/5 * * * *", "agent": "crypto_monitor", "mode": "code"},
        
        # 🎯 Polymarket Arbitrage — кожні 30 хв
        {"job": polymarket_scan_job, "cron": "*/30 * * * *", "agent": "polymarket_analyzer", "mode": "code"},
        
        # 🔍 Deep Scan — кожні 2 год
        {"job": polymarket_depth_job, "cron": "0 */2 * * *", "agent": "polymarket_analyzer", "mode": "code"},
        
        # 📰 News Linker — кожні 6 год
        {"job": polymarket_news_job, "cron": "0 */6 * * *", "agent": "polymarket_analyzer", "mode": "code"},
        
        # 👁️ Topic Monitor — кожні 4 год
        {"job": polymarket_topic_job, "cron": "0 */4 * * *", "agent": "polymarket_analyzer", "mode": "code"},
        
        # 📊 Weekly Calibration — понеділок 10:00
        {"job": weekly_calibration_job, "cron": "0 10 * * 1", "agent": "mirofish", "mode": "code"},
        
        # 📊 Auto Sentiment Scan — кожні 6 год
        {"job": auto_sentiment_job, "cron": "0 */6 * * *", "agent": "mirofish", "mode": "orchestrate"},
        
        # 🎯 Auto Prediction Packet — кожні 12 год
        {"job": auto_prediction_job, "cron": "0 */12 * * *", "agent": "mirofish", "mode": "orchestrate"},
        
        # 🤖 Dashboard — кожні 30 хв
        {"job": dashboard_job, "cron": "*/30 * * * *", "agent": "mirofish", "mode": "ask"},
    ]
    
    build_rooflow_scheduler(sched, jobs_config)

    console.print("[bold green]🚀 Scheduler started.[/] 7 Skills активні:")
    console.print(f"  Всього jobs: {len(jobs_config)}")
    for job in sched.get_jobs():
        console.print(f"  • {job.name} → {job.trigger}")
    
    # Оновити activeContext для всіх агентів
    engine = RooFlowEngine()
    for agent in ("english_bot", "crypto_monitor", "polymarket_analyzer", "mirofish"):
        engine.append_memory_bank(
            agent, "activeContext.md",
            f"\n- **{datetime.utcnow().isoformat()[:19]}** — 7-Skill Scheduler started\n"
            f"  - Активні jobs: {len(jobs_config)}\n"
            f"  - Режим: {engine.get_mode(agent)}\n"
        )
    
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


@app.command("skills")
def list_skills() -> None:
    """Перелік skills, доступних для Hermes Dashboard."""
    from hermes_integration import HermesExecutor
    table = Table(title="Hermes Skills")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Enabled")
    table.add_column("Description")
    for s in HermesExecutor().list_skills():
        table.add_row(s["id"], s["name"], "✅" if s["enabled"] else "❌", s["description"])
    console.print(table)


if __name__ == "__main__":
    app()
