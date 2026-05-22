"""Tests for Event Bus and Reaction Engine."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from coordination.event_bus import AgentBus, SignalEvent, get_bus
from coordination.reaction_engine import ReactionEngine, get_engine


# --------------------------------------------------------------------------- #
class TestEventBus:
    def test_singleton(self):
        b1 = get_bus()
        b2 = get_bus()
        assert b1 is b2

    def test_publish_and_subscribe(self):
        bus = AgentBus()
        bus._subs.clear()  # clean for test
        received = []

        def handler(event: SignalEvent):
            received.append(event)

        bus.subscribe("test.topic", handler)
        event = SignalEvent(source="test", topic="test.topic", payload={"x": 1}, priority=0)
        bus.publish(event)

        assert len(received) == 1
        assert received[0].payload["x"] == 1
        assert received[0].source == "test"

    def test_multiple_subscribers(self):
        bus = AgentBus()
        bus._subs.clear()
        received1, received2 = [], []

        bus.subscribe("test.multi", lambda e: received1.append(e.source))
        bus.subscribe("test.multi", lambda e: received2.append(e.topic))

        bus.publish(SignalEvent(source="a", topic="test.multi", payload={}, priority=0))

        assert received1 == ["a"]
        assert received2 == ["test.multi"]

    def test_no_subscriber_no_crash(self):
        bus = AgentBus()
        bus._subs.clear()
        # publish without subscribers — should not crash
        bus.publish(SignalEvent(source="a", topic="test.empty", payload={}, priority=0))

    def test_priority_critical(self):
        event = SignalEvent(source="t", topic="t", payload={}, priority=2)
        assert event.is_critical()

        event0 = SignalEvent(source="t", topic="t", payload={}, priority=0)
        assert not event0.is_critical()


# --------------------------------------------------------------------------- #
class TestReactionEngine:
    def test_singleton(self):
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2

    def test_start_subscribes_topics(self):
        engine = ReactionEngine()
        engine._started = False
        engine.start()
        assert engine._started

    def test_stop_unsubscribes(self):
        engine = ReactionEngine()
        engine._started = True
        engine.stop()
        assert not engine._started

    def test_on_handler(self):
        engine = ReactionEngine()
        actions = []

        def handler(action):
            actions.append(action.action_type)

        engine.on("test", handler)
        from dataclasses import dataclass
        from coordination.reaction_engine import Action
        import time

        a = Action(agent="t", action_type="test", payload={}, created_at=time.time())
        engine._dispatch(a)
        assert actions == ["test"]

    def test_fast_mover_reaction(self):
        engine = ReactionEngine()
        engine._started = False
        engine.start()
        # Simulate receiving crypto.fast_mover event
        bus = get_bus()
        bus.publish(
            SignalEvent(
                source="crypto_monitor",
                topic="crypto.fast_mover",
                payload={
                    "symbol": "BTC",
                    "pct_change": 25.0,
                    "window": "1h",
                },
                priority=2,
            )
        )
        # Should have generated actions
        assert len(engine.actions()) > 0
        stats = engine.stats()
        assert stats["started"]
        assert stats["total_actions"] > 0

    def test_arb_reaction(self):
        engine = ReactionEngine()
        engine._started = False
        engine.start()
        bus = get_bus()
        bus.publish(
            SignalEvent(
                source="polymarket_analyzer",
                topic="polymarket.arb",
                payload={
                    "question": "Will BTC > 100k?",
                    "edge": 0.04,
                    "safe_to_trade": True,
                    "recommended_usd": 500,
                    "resolution_risk": 0.1,
                },
                priority=1,
            )
        )
        stats = engine.stats()
        assert stats["total_actions"] > 0

    def test_stats(self):
        engine = ReactionEngine()
        stats = engine.stats()
        assert "total_actions" in stats
        assert "by_type" in stats
        assert "started" in stats
