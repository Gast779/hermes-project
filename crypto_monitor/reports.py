"""Генератор звітів по крипті."""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from .data_sources import CoinGeckoClient, CoinTicker

log = logging.getLogger(__name__)


def _fmt_money(v: float) -> str:
    if v >= 1e12:
        return f"${v / 1e12:.2f}T"
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.2f}M"
    if v >= 1e3:
        return f"${v / 1e3:.2f}K"
    return f"${v:,.2f}"


def _fmt_price(v: float) -> str:
    if v >= 100:
        return f"${v:,.2f}"
    if v >= 1:
        return f"${v:.4f}"
    if v >= 0.01:
        return f"${v:.6f}"
    return f"${v:.8f}"


def _coin_row(c: CoinTicker) -> str:
    p24 = f"{c.pct_change_24h:+.2f}%" if c.pct_change_24h is not None else "—"
    return f"| {c.symbol} | {_fmt_price(c.price_usd)} | {p24} | {_fmt_money(c.total_volume_usd)} |"


def generate_daily_report(
    cg: CoinGeckoClient,
    *,
    timezone: str = "Europe/Kyiv",
    top_n: int = 10,
) -> str:
    """Повертає markdown-звіт."""
    now = datetime.now(ZoneInfo(timezone))
    g = cg.get_global()
    top = cg.get_top_markets(per_page=top_n, page=1, price_change="1h,24h,7d")
    gainers, losers = cg.get_movers()

    total_cap = (g.get("total_market_cap") or {}).get("usd", 0)
    total_vol = (g.get("total_volume") or {}).get("usd", 0)
    btc_dom = (g.get("market_cap_percentage") or {}).get("btc")
    eth_dom = (g.get("market_cap_percentage") or {}).get("eth")
    cap_change_24h = g.get("market_cap_change_percentage_24h_usd")

    lines: list[str] = [
        f"# 🪙 Crypto Market Report — {now.strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        "## Загальний стан",
        "",
        f"- **Total market cap:** {_fmt_money(total_cap)} "
        + (f"({cap_change_24h:+.2f}% за 24h)" if cap_change_24h is not None else ""),
        f"- **24h volume:** {_fmt_money(total_vol)}",
        f"- **BTC dominance:** {btc_dom:.2f}%" if btc_dom else "",
        f"- **ETH dominance:** {eth_dom:.2f}%" if eth_dom else "",
        "",
        f"## Топ {top_n} монет",
        "",
        "| Symbol | Price | 24h | Volume |",
        "|--------|-------|-----|--------|",
        *[_coin_row(c) for c in top],
        "",
        "## 🚀 Top 24h gainers",
        "",
        "| Symbol | Price | 24h | Volume |",
        "|--------|-------|-----|--------|",
        *[_coin_row(c) for c in gainers],
        "",
        "## 📉 Top 24h losers",
        "",
        "| Symbol | Price | 24h | Volume |",
        "|--------|-------|-----|--------|",
        *[_coin_row(c) for c in losers],
        "",
    ]

    try:
        trending = cg.get_trending()
        if trending:
            lines += [
                "## 🔥 Trending (за пошуками на CoinGecko)",
                "",
                ", ".join(
                    f"`{t.get('item', {}).get('symbol', '?')}`"
                    for t in trending[:10]
                ),
                "",
            ]
    except Exception as e:        # noqa: BLE001
        log.warning("Trending fetch failed: %s", e)

    lines.append("_Дані: CoinGecko. Звіт згенеровано автоматично Hermes Crypto Monitor._")
    return "\n".join(filter(None, lines))
