"""
Hermes — головна CLI-точка входу.

Команди:
    python main.py polymarket scan                       # одноразовий пошук арбітражу
    python main.py polymarket monitor "trump"            # моніторинг ринків за темою
    python main.py polymarket realtime --tokens 0x... 0x...
    python main.py polymarket cross                      # крос-маркет з Kalshi
    python main.py crypto report                         # одноразовий звіт
    python main.py crypto watch                          # daemon: fast movers
    python main.py english lesson [grammar|vocab|speak]  # генерація уроку
    python main.py english chat                          # інтерактивний REPL
    python main.py scheduler                             # повний розклад
"""
from __future__ import annotations

import asyncio
import logging
import sys
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
from english_bot import EnglishBot, GrokClient, LessonPlanner, LessonType
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

setup_logging()
log = logging.getLogger("hermes")
console = Console()

app = typer.Typer(no_args_is_help=True, help="Hermes Multi-Agent System")
poly = typer.Typer(help="Polymarket аналітика")
crypto = typer.Typer(help="Криптовалютні звіти та алерти")
english = typer.Typer(help="Тренер англійської")
app.add_typer(poly, name="polymarket")
app.add_typer(crypto, name="crypto")
app.add_typer(english, name="english")


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
    send_telegram(text)


@crypto.command("watch")
def crypto_watch() -> None:
    """Daemon: моніторинг fast-movers (Ctrl-C — стоп)."""
    crypto_watch_loop()


def crypto_watch_loop() -> None:
    cfg = settings()["crypto_monitor"]["alerts"]
    cg = _make_cg()
    watcher = FastMoversWatcher(
        cg,
        callback=_alert_callback,
        pct_5m=cfg["thresholds"]["pct_5m"],
        pct_1h=cfg["thresholds"]["pct_1h"],
        poll_interval_seconds=cfg["poll_interval_seconds"],
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
    api_key = env("XAI_API_KEY", required=True)
    model = settings()["english_bot"]["grok_model"]
    grok = GrokClient(api_key=api_key, model=model)
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


# Entry points для Hermes:
def english_chat_skill() -> None:
    """Hermes skill: open chat session."""
    english_chat()


def polymarket_scan_job() -> None:
    """Hermes skill: scheduled scan + telegram."""
    with PolymarketClient() as client:
        cfg = settings()["polymarket"]["arbitrage"]
        finder = InternalArbitrageFinder(
            client, min_edge=cfg["min_edge"], min_volume_usd=cfg["min_volume_usd"]
        )
        opps = finder.find()
    if opps:
        send_telegram(format_arbitrage_report(opps))


def polymarket_topic_job(keyword: str = "trump") -> None:
    """Hermes skill: scheduled topic monitor tick."""
    with PolymarketClient() as client:
        mon = TopicMonitor(client, keyword)
        report = mon.tick()
    if report.arbitrage or report.significant_changes:
        send_telegram(format_topic_report(report))


# =========================================================================== #
# SCHEDULER
# =========================================================================== #
@app.command("scheduler")
def run_scheduler() -> None:
    """Запустити всі завдання за розкладом (blocking)."""
    tz = settings()["general"]["timezone"]
    sched = build_scheduler(timezone=tz)

    # Crypto reports
    for cron in settings()["crypto_monitor"]["report_schedule"]:
        add_cron_job(sched, crypto_report_job, cron, name=f"crypto-report-{cron}")

    # Polymarket arbitrage scan
    add_cron_job(sched, polymarket_scan_job, "*/30 * * * *", name="polymarket-scan")

    # Fast movers — окремий процес, бо це не cron, а daemon.
    # Запускай окремо: `python main.py crypto watch`.

    console.print("[bold green]Scheduler started.[/] Активні задачі:")
    for job in sched.get_jobs():
        console.print(f"  • {job.name} → {job.trigger}")
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
