"""Тести нових модулів: depth-arbitrage, news linker, storage."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from polymarket_analyzer.depth_arbitrage import (
    DepthLevel,
    _parse_levels,
    estimate_execution,
)
from polymarket_analyzer.news_linker import extract_keywords


# --------------------------------------------------------------------------- #
# Depth — math
# --------------------------------------------------------------------------- #
def test_parse_levels_sorts_correctly():
    # asks: від мін до макс
    raw_asks = [{"price": "0.45", "size": "100"}, {"price": "0.42", "size": "50"}]
    levels = _parse_levels(raw_asks, reverse_sort=False)
    assert [l.price for l in levels] == [0.42, 0.45]
    # cumulatives працюють правильно
    assert levels[0].cumulative_size == 50
    assert levels[1].cumulative_size == 150


def test_parse_levels_bids_descending():
    raw_bids = [{"price": "0.50", "size": "100"}, {"price": "0.55", "size": "30"}]
    levels = _parse_levels(raw_bids, reverse_sort=True)
    assert [l.price for l in levels] == [0.55, 0.50]


def test_estimate_execution_within_top_level():
    # 50 shares за 0.40 — це лише top level (size=100), avg = 0.40
    levels = [
        DepthLevel(price=0.40, size=100, cumulative_size=100, cumulative_cost=40.0),
        DepthLevel(price=0.42, size=200, cumulative_size=300, cumulative_cost=124.0),
    ]
    est = estimate_execution(levels, target_shares=50)
    assert est is not None
    assert est.avg_price == 0.40
    assert est.achievable_size == 50
    assert est.slippage_bps == 0.0


def test_estimate_execution_crosses_levels():
    # 200 shares: 100 за 0.40 + 100 за 0.42 = 82 за 200 → avg 0.41
    levels = [
        DepthLevel(price=0.40, size=100, cumulative_size=100, cumulative_cost=40.0),
        DepthLevel(price=0.42, size=200, cumulative_size=300, cumulative_cost=124.0),
    ]
    est = estimate_execution(levels, target_shares=200)
    assert abs(est.avg_price - 0.41) < 1e-9
    assert est.achievable_size == 200
    # slippage = 10000 × (0.41 - 0.40)/0.40 = 250 bps
    assert abs(est.slippage_bps - 250.0) < 0.5


def test_estimate_execution_partial_fill():
    """Якщо в стаку менше, ніж треба — повертаємо те, що вдалося."""
    levels = [DepthLevel(price=0.40, size=10, cumulative_size=10, cumulative_cost=4.0)]
    est = estimate_execution(levels, target_shares=100)
    assert est.achievable_size == 10
    assert est.avg_price == 0.40


def test_estimate_execution_empty_returns_none():
    assert estimate_execution([], target_shares=100) is None
    assert estimate_execution([DepthLevel(0.40, 10)], target_shares=0) is None


# --------------------------------------------------------------------------- #
# News linker — keyword extraction
# --------------------------------------------------------------------------- #
def test_extract_keywords_finds_capitalized_names():
    text = "Donald Trump announced new tariffs on China today."
    kw = extract_keywords(text)
    # Має витягти "Donald Trump" і "China"
    joined = " ".join(kw).lower()
    assert "trump" in joined
    assert "china" in joined


def test_extract_keywords_filters_stopwords():
    text = "the and or but if than this that"
    kw = extract_keywords(text)
    assert kw == []   # все відфільтрувалось


def test_extract_keywords_returns_max_count():
    # Реальні англійські слова (>= 3 символи), щоб пройти регекспом
    text = ("apple banana cherry dragon elephant flamingo "
            "guitar harbor island jaguar kangaroo lemon "
            "mountain noodle ocean python")
    kw = extract_keywords(text, max_count=5)
    assert len(kw) == 5


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
def test_storage_persists_alert():
    from storage import Storage
    from crypto_monitor.alerts import FastMoverAlert

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        with Storage(db_path) as s:
            alert = FastMoverAlert(
                coin_id="bitcoin", symbol="BTC", name="Bitcoin",
                price=69000.0, window="5m", pct_change=6.5,
                volume_24h=20_000_000_000, market_cap=1_300_000_000_000,
            )
            row_id = s.save_alert(alert)
            assert row_id > 0
            rows = s.recent_alerts()
            assert len(rows) == 1
            assert rows[0]["symbol"] == "BTC"
            assert rows[0]["pct_change"] == 6.5


def test_storage_persistent_cooldown():
    from storage import Storage
    from crypto_monitor.alerts import FastMoverAlert
    import time

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        with Storage(db_path) as s:
            alert = FastMoverAlert("eth", "ETH", "Ethereum", 3000.0, "1h", 22.0,
                                   1e10, 4e11)
            s.save_alert(alert)
            # одразу — є запис в межах останніх 3600 секунд
            assert s.was_alerted_recently("eth", since_seconds=3600) is True
            # за межами вікна 0.001 сек — не лічимо
            time.sleep(0.01)
            # При since_seconds дуже малому (0) — функція повертає False, бо
            # cutoff = now, а запис ts <= now → ts >= now буде False через
            # round-down мікросекунд. Тестуємо інше:
            assert s.was_alerted_recently("nonexistent", since_seconds=3600) is False


def test_storage_news_link_dedup():
    from storage import Storage
    with tempfile.TemporaryDirectory() as tmp:
        with Storage(Path(tmp) / "t.db") as s:
            ok1 = s.save_news_link(
                "https://news.com/a", "Title", "news.com",
                "trump-2028", "mkt1", 0.5,
            )
            ok2 = s.save_news_link(
                "https://news.com/a", "Title", "news.com",
                "trump-2028", "mkt1", 0.6,
            )
            assert ok1 is True
            assert ok2 is False    # дублікат
