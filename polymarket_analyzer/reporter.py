"""Форматування звітів по Polymarket у Markdown."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .arbitrage_internal import ArbitrageOpportunity
from .cross_market import Discrepancy
from .topic_monitor import TopicReport


KB_PATH = Path(__file__).parent.parent / "hermes_knowledge_base.db"


def _get_translation(en_text: str, table: str = "market_translations") -> str:
    """Переклад з KB. Якщо нема — повертає оригінал."""
    try:
        conn = sqlite3.connect(KB_PATH)
        cur = conn.execute(f"SELECT uk FROM {table} WHERE en = ?", (en_text,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else en_text
    except Exception:
        return en_text


# --------------------------------------------------------------------------- #
def _short_question(q: str, n: int = 80) -> str:
    return q if len(q) <= n else q[: n - 1] + "…"


def _slug_url(slug: str) -> str:
    return f"https://polymarket.com/event/{slug}" if slug else ""


# --------------------------------------------------------------------------- #
def format_arbitrage_report(opps: Iterable[ArbitrageOpportunity]) -> str:
    opps = list(opps)
    if not opps:
        return ""
    lines = [
        "## 🟢 Polymarket: внутрішній арбітраж (v2 — fee-aware + safety)",
        "",
        f"Знайдено **{len(opps)}** можливостей. Топ:",
        "",
        "| # | Edge | Тип | Ринок | ∑ask | ∑bid | Volume | Risk | Sizing |",
        "|---|------|-----|-------|------|------|--------|------|--------|",
    ]
    for i, o in enumerate(opps[:25], 1):
        url = _slug_url(o.slug)
        title = f"[{_short_question(o.question, 50)}]({url})" if url else _short_question(o.question, 50)
        sum_a = f"{o.sum_asks:.4f}" if o.sum_asks is not None else "—"
        sum_b = f"{o.sum_bids:.4f}" if o.sum_bids is not None else "—"
        risk = "🟢" if getattr(o, "safe_to_trade", True) else "🔴"
        sizing = getattr(o, "recommended_usd", None)
        sizing_str = f"${sizing:.0f}" if sizing else "-"
        lines.append(
            f"| {i} | **{o.edge:+.2%}** | {o.kind} | {title} | {sum_a} | {sum_b} "
            f"| ${o.volume_usd:,.0f} | {risk} | {sizing_str} |"
        )
    lines.append("")
    lines.append(
        "> _Edge — потенційний прибуток на 1 USDC. Не враховує slippage й fees. "
        "🟢 = safe_to_trade, 🔴 = resolution risk високий._"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
def format_topic_report(report: TopicReport) -> str:
    lines = [
        f"## 🔍 Polymarket — моніторинг теми: `{report.keyword}`",
        "",
        f"Активних ринків: **{len(report.markets)}**.",
        "",
    ]
    if report.markets:
        lines += [
            "### Топ-10 ринків за обʼємом",
            "",
            "| Ринок | Outcomes (поточні ціни) | Volume |",
            "|-------|--------------------------|--------|",
        ]
        for m in sorted(report.markets, key=lambda x: x.volume_usd, reverse=True)[:10]:
            url = _slug_url(m.slug)
            title_en = _short_question(m.question, 60)
            title_uk = _get_translation(m.question)
            if title_uk != m.question:
                title = f"[{title_en}]({url})\n   _{title_uk}_" if url else f"{title_en}\n   _{title_uk}_"
            else:
                title = f"[{title_en}]({url})" if url else title_en
            outc = " / ".join(
                f"{o.name}: `{o.price:.3f}`" if o.price is not None else f"{o.name}: —"
                for o in m.outcomes
            )
            lines.append(f"| {title} | {outc} | ${m.volume_usd:,.0f} |")
        lines.append("")

    lines.append(f"👁️ Моніторинг активний: {len(report.markets)} ринків за ключовим словом «{report.keyword}» відстежуються.")

    if report.significant_changes:
        lines += [
            "### ⚡ Помітні зміни цін з минулого тіку",
            "",
            "| Ринок | Outcome | Було | Стало | Δ | За скільки сек |",
            "|-------|---------|------|-------|---|----------------|",
        ]
        for c in report.significant_changes[:15]:
            lines.append(
                f"| {_short_question(c['market'], 50)} | {c['outcome']} "
                f"| `{c['from']:.3f}` | `{c['to']:.3f}` | **{c['diff']:+.3f}** "
                f"| {int(c['dt_seconds'])}s |"
            )
        lines.append("")

    if report.arbitrage:
        lines.append(format_arbitrage_report(report.arbitrage))
    else:
        pass  # No arbitrage — silent

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
def format_cross_market_report(discrepancies: Iterable[Discrepancy]) -> str:
    items = list(discrepancies)
    if not items:
        return ""  # No data — silent
    lines = [
        "## 🔀 Crossmarket: Polymarket vs зовнішні",
        "",
        f"Знайдено **{len(items)}** розбіжностей ≥ порогу:",
        "",
        "| Outcome | Polymarket | External | Δ | Sim | Питання |",
        "|---------|------------|----------|---|-----|---------|",
    ]
    for d in items[:25]:
        lines.append(
            f"| {d.outcome} | `{d.pm_prob:.3f}` | `{d.ext_prob:.3f}` ({d.source}) "
            f"| **{d.diff:+.3f}** | {d.topic_similarity:.0%} "
            f"| {_short_question(d.polymarket_question, 60)} |"
        )
    lines += [
        "",
        "> Sim — наскільки схожі формулювання питань (fuzzy match). "
        "Перш ніж торгувати — перевір правила resolution!",
    ]
    return "\n".join(lines)
