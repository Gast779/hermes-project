"""
Тести математики арбітражу — без виходу в мережу.
"""
from __future__ import annotations

from polymarket_analyzer.arbitrage_internal import InternalArbitrageFinder
from polymarket_analyzer.client import Market, Outcome, PolymarketClient


class _StubClient(PolymarketClient):
    """Не робить HTTP-запитів. Підставляємо готові bid/ask."""

    def __init__(self, prices: dict[str, tuple[float, float]]):
        self._prices = prices

    def fetch_best_prices(self, token_id: str):
        return self._prices.get(token_id, (None, None))

    def enrich_market_with_book(self, market: Market) -> Market:
        for o in market.outcomes:
            o.best_bid, o.best_ask = self.fetch_best_prices(o.token_id)
        return market


def _make_market(outcomes: list[tuple[str, str]], volume: float = 50_000) -> Market:
    """outcomes = [(token_id, name), ...]"""
    return Market(
        id="test",
        condition_id="cond",
        question="Test market?",
        slug="test-market",
        outcomes=[Outcome(token_id=tid, name=name, price=0.5) for tid, name in outcomes],
        volume_usd=volume,
    )


def test_buy_arbitrage_detected():
    # Yes ask = 0.40, No ask = 0.50 → sum = 0.90 → buy_edge = 0.10
    client = _StubClient({
        "yes": (0.39, 0.40),
        "no":  (0.49, 0.50),
    })
    market = _make_market([("yes", "Yes"), ("no", "No")])
    finder = InternalArbitrageFinder(client, min_edge=0.01, min_volume_usd=0)
    opp = finder.analyze_market(market)
    assert opp is not None
    assert opp.kind == "buy_all"
    assert abs(opp.edge - 0.10) < 1e-9
    assert abs(opp.sum_asks - 0.90) < 1e-9


def test_sell_arbitrage_detected():
    # Yes bid = 0.60, No bid = 0.55 → sum = 1.15 → sell_edge = 0.15
    client = _StubClient({
        "yes": (0.60, 0.61),
        "no":  (0.55, 0.56),
    })
    market = _make_market([("yes", "Yes"), ("no", "No")])
    finder = InternalArbitrageFinder(client, min_edge=0.01, min_volume_usd=0)
    opp = finder.analyze_market(market)
    assert opp is not None
    assert opp.kind == "sell_all"
    assert abs(opp.edge - 0.15) < 1e-9


def test_no_arbitrage_fair_market():
    # ∑ask = 1.02, ∑bid = 0.98 → нічого
    client = _StubClient({
        "yes": (0.50, 0.51),
        "no":  (0.48, 0.51),
    })
    market = _make_market([("yes", "Yes"), ("no", "No")])
    finder = InternalArbitrageFinder(client, min_edge=0.01, min_volume_usd=0)
    assert finder.analyze_market(market) is None


def test_volume_filter_excludes_thin_markets():
    client = _StubClient({"yes": (0.39, 0.40), "no": (0.49, 0.50)})
    market = _make_market([("yes", "Yes"), ("no", "No")], volume=100)  # < 1000
    finder = InternalArbitrageFinder(client, min_edge=0.01, min_volume_usd=1000)
    assert finder.analyze_market(market) is None


def test_fees_eat_thin_edge():
    # sum_asks = 0.99 → buy_edge = 0.01. З fee 0.005 на сторону (×2 outcomes = 0.01) edge = 0.
    client = _StubClient({"yes": (0.48, 0.49), "no": (0.49, 0.50)})
    market = _make_market([("yes", "Yes"), ("no", "No")])
    finder = InternalArbitrageFinder(client, min_edge=0.005, min_volume_usd=0, fee_per_side=0.005)
    opp = finder.analyze_market(market)
    # 1 - 0.99 - 0.01 = 0; min_edge=0.005 → None
    assert opp is None


def test_multi_outcome_arbitrage():
    # 3 outcomes: 0.30 + 0.30 + 0.30 = 0.90 → buy_edge = 0.10
    client = _StubClient({
        "a": (0.29, 0.30),
        "b": (0.29, 0.30),
        "c": (0.29, 0.30),
    })
    market = _make_market([("a", "A"), ("b", "B"), ("c", "C")])
    finder = InternalArbitrageFinder(client, min_edge=0.01, min_volume_usd=0)
    opp = finder.analyze_market(market)
    assert opp is not None
    assert opp.kind == "buy_all"
    assert abs(opp.edge - 0.10) < 1e-9
