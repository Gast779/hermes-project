"""Tests for Coordinator Agent (Phase 5)."""

from __future__ import annotations

import pytest

from coordination.coordinator import CoordinatorAgent, FactorScore, CompositeResult, get_coordinator


# --------------------------------------------------------------------------- #
class TestCoordinator:
    def test_singleton(self):
        c1 = get_coordinator()
        c2 = get_coordinator()
        assert c1 is c2

    def test_empty_composite(self):
        coord = CoordinatorAgent()
        result = coord.compute_composite()
        assert isinstance(result, CompositeResult)
        assert 0 <= result.total_score <= 1
        assert result.signal in ("strong_buy", "buy", "neutral", "sell")
        assert result.factors == []

    def test_polymarket_factor(self):
        coord = CoordinatorAgent()
        from coordination.event_bus import SignalEvent
        coord._latest["polymarket.arb"] = SignalEvent(
            source="test",
            topic="polymarket.arb",
            payload={"edge": 0.04, "question": "Will BTC hit 100k?"},
            priority=1,
        )
        result = coord.compute_composite()
        assert len(result.factors) >= 1
        assert any(f.factor == "polymarket_arb" for f in result.factors)
        assert result.total_score > 0

    def test_crypto_factor(self):
        coord = CoordinatorAgent()
        from coordination.event_bus import SignalEvent
        coord._latest["crypto.fast_mover"] = SignalEvent(
            source="test",
            topic="crypto.fast_mover",
            payload={"symbol": "SOL", "pct_change": 15.5},
            priority=1,
        )
        result = coord.compute_composite()
        assert any(f.factor == "crypto_fast_mover" for f in result.factors)

    def test_whale_factor(self):
        coord = CoordinatorAgent()
        from coordination.event_bus import SignalEvent
        coord._latest["crypto.whale"] = SignalEvent(
            source="test",
            topic="crypto.whale",
            payload={"value_usd": 5_000_000, "direction": "inflow"},
            priority=0,
        )
        result = coord.compute_composite()
        assert any(f.factor == "crypto_whale" for f in result.factors)

    def test_lp_factor(self):
        coord = CoordinatorAgent()
        from coordination.event_bus import SignalEvent
        coord._latest["lp.opportunity"] = SignalEvent(
            source="test",
            topic="lp.opportunity",
            payload={"name": "ETH-USDC", "apy": 12.5, "risk_score": 0.1},
            priority=0,
        )
        result = coord.compute_composite()
        assert any(f.factor == "lp_yield" for f in result.factors)

    def test_deribit_factor(self):
        coord = CoordinatorAgent()
        from coordination.event_bus import SignalEvent
        coord._latest["strategies.deribit"] = SignalEvent(
            source="test",
            topic="strategies.deribit",
            payload={"basis_percent": 1.5, "symbol": "BTC-PERP"},
            priority=1,
        )
        result = coord.compute_composite()
        assert any(f.factor == "strategies_deribit" for f in result.factors)

    def test_strong_buy_signal(self):
        coord = CoordinatorAgent()
        from coordination.event_bus import SignalEvent
        coord._latest["polymarket.arb"] = SignalEvent(
            source="test",
            topic="polymarket.arb",
            payload={"edge": 0.10},
            priority=2,
        )
        coord._latest["strategies.deribit"] = SignalEvent(
            source="test",
            topic="strategies.deribit",
            payload={"basis_percent": 2.0},
            priority=2,
        )
        result = coord.compute_composite()
        assert result.signal == "strong_buy"
        assert result.total_score >= 0.7

    def test_digest_generation(self):
        coord = CoordinatorAgent()
        from coordination.event_bus import SignalEvent
        coord._latest["polymarket.arb"] = SignalEvent(
            source="test",
            topic="polymarket.arb",
            payload={"edge": 0.05},
            priority=1,
        )
        text = coord.generate_digest()
        assert "Composite Digest" in text
        assert "Фактори" in text

    def test_history_save_and_load(self):
        coord = CoordinatorAgent()
        from coordination.event_bus import SignalEvent
        coord._latest["polymarket.arb"] = SignalEvent(
            source="test",
            topic="polymarket.arb",
            payload={"edge": 0.05},
            priority=1,
        )
        coord.compute_composite()
        history = coord.get_history(last_n=5)
        assert len(history) >= 1
        assert "signal" in history[-1]
        assert "total_score" in history[-1]

    def test_top_opportunities(self):
        coord = CoordinatorAgent()
        from coordination.event_bus import SignalEvent
        coord._latest["polymarket.arb"] = SignalEvent(
            source="test",
            topic="polymarket.arb",
            payload={"edge": 0.05, "question": "BTC 100k?"},
            priority=2,
        )
        result = coord.compute_composite()
        assert len(result.top_opportunities) >= 1
        assert result.top_opportunities[0]["type"] == "polymarket_arb"
