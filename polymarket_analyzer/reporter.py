"""Форматування звітів по Polymarket у Markdown."""
from __future__ import annotations

from typing import Iterable

from .arbitrage_internal import ArbitrageOpportunity
from .cross_market import Discrepancy
from .topic_monitor import TopicReport


# --------------------------------------------------------------------------- #
def _short_question(q: str, n: int = 80) -> str:
    return q if len(q) <= n else q[: n - 1] + "…"


def _slug_url(slug: str) -> str:
    return f"https://polymarket.com/event/{slug}" if slug else ""


# --------------------------------------------------------------------------- #
def format_arbitrage_report(opps: Iterable[ArbitrageOpportunity]) -> str:
    opps = list(opps)
    if not opps:
        return ""  # No data — silent
    lines = [
        "## 🟢 Polymarket: внутрішній арбітраж",
        "",
        f"Знайдено **{len(opps)}** можливостей. Топ:",
        "",
        "| # | Edge | Тип | Ринок | ∑ask | ∑bid | Volume |",
        "|---|------|-----|-------|------|------|--------|",
    ]
    for i, o in enumerate(opps[:25], 1):
        url = _slug_url(o.slug)
        title = f"[{_short_question(o.question, 55)}]({url})" if url else _short_question(o.question, 55)
        sum_a = f"{o.sum_asks:.4f}" if o.sum_asks is not None else "—"
        sum_b = f"{o.sum_bids:.4f}" if o.sum_bids is not None else "—"
        lines.append(
            f"| {i} | **{o.edge:+.2%}** | {o.kind} | {title} | {sum_a} | {sum_b} | ${o.volume_usd:,.0f} |"
        )
    lines.append("")
    lines.append("> _Edge — потенційний прибуток на 1 USDC. Не враховує slippage й fees._")
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
            title = f"[{_short_question(m.question, 60)}]({url})" if url else _short_question(m.question, 60)
            outc = " / ".join(
                f"{o.name}: `{o.price:.3f}`" if o.price is not None else f"{o.name}: —"
                for o in m.outcomes
            )
            lines.append(f"| {title} | {outc} | ${m.volume_usd:,.0f} |")
        lines.append("")

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
