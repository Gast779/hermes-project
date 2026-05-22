"""Tests for Backtest Framework: recorder, metrics, evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from backtest.metrics import SignalMetrics, calculate_metrics
from backtest.recorder import BacktestRecorder, RecordedSignal
from backtest.evaluator import StrategyEvaluator, DailyStats


# --------------------------------------------------------------------------- #
class FakeSignal:
    """Мінімальний сигнал edge + recommended."""
    def __init__(self, edge: float | None = None, recommended_usd: float | None = None):
        self.edge = edge
        self.recommended_usd = recommended_usd


class TestMetrics:
    def test_empty_signals(self):
        m = calculate_metrics([])
        assert m.total == 0
        assert m.win_rate == 0.0
        assert m.sharpe_ratio is None

    def test_basic_win(self):
        # 2 signals, обидва з edge > 0
        signals = [FakeSignal(edge=0.05), FakeSignal(edge=0.03)]
        m = calculate_metrics(signals)
        assert m.total == 2
        assert m.winning == 2
        assert m.win_rate == 1.0
        assert m.avg_edge == pytest.approx(0.04)
        assert m.max_edge == pytest.approx(0.05)
        assert m.sharpe_ratio is not None

    def test_mixed_win_lose(self):
        signals = [FakeSignal(edge=0.05), FakeSignal(edge=-0.02), FakeSignal(edge=0.01)]
        m = calculate_metrics(signals)
        assert m.total == 3
        assert m.winning == 2
        assert m.losing == 1
        assert m.win_rate == pytest.approx(2 / 3)
        assert m.profit_factor is not None

    def test_no_sharpe_single_signal(self):
        signals = [FakeSignal(edge=0.05)]
        m = calculate_metrics(signals)
        assert m.sharpe_ratio is None  # < 2 signals

    def test_size_metrics(self):
        signals = [FakeSignal(edge=0.05, recommended_usd=500), FakeSignal(edge=0.03, recommended_usd=300)]
        m = calculate_metrics(signals)
        assert m.avg_recommended_usd == 400.0
        assert m.total_recommended_usd == 800.0
        assert m.max_recommended_usd == 500.0


# --------------------------------------------------------------------------- #
class TestRecorder:
    def test_singleton(self):
        r1 = BacktestRecorder()
        r2 = BacktestRecorder()
        assert r1 is r2

    def test_record_and_query(self):
        rec = BacktestRecorder()
        # use fresh in-memory or clean db for test
        from coordination.event_bus import SignalEvent
        rec.record(SignalEvent(source="t", topic="t.t", payload={"edge": 0.05}, priority=0))
        rec.record(SignalEvent(source="t", topic="t.t", payload={"edge": 0.03}, priority=0))
        sigs = rec.get_signals(topic="t.t", limit=10)
        assert len(sigs) == 2

    def test_infer_strategy_arb(self):
        rec = BacktestRecorder()
        from coordination.event_bus import SignalEvent
        s = SignalEvent(source="p", topic="polymarket.arb", payload={}, priority=0)
        assert rec._infer_strategy(s) == "polymarket_arb"

    def test_infer_strategy_crypto(self):
        rec = BacktestRecorder()
        from coordination.event_bus import SignalEvent
        s = SignalEvent(source="c", topic="crypto.fast_mover", payload={}, priority=0)
        assert rec._infer_strategy(s) == "crypto_fast_mover"

    def test_count_and_prune(self):
        rec = BacktestRecorder()
        initial = rec.count()
        from coordination.event_bus import SignalEvent
        rec.record(SignalEvent(source="t", topic="t", payload={}, priority=0))
        assert rec.count() == initial + 1
        pruned = rec.prune(older_than_days=-1)  # prune everything older than now
        # should prune everything (since all records are from now)
        assert pruned >= initial + 0


# --------------------------------------------------------------------------- #
class TestEvaluator:
    def test_evaluate_empty(self):
        ev = StrategyEvaluator()
        report = ev.evaluate(strategy="test_strategy", days=7)
        assert report.strategy == "test_strategy"
        assert report.metrics.total == 0
        assert report.drawdown is None

    def test_evaluate_with_signals(self):
        ev = StrategyEvaluator()
        # inject signals via recorder
        from coordination.event_bus import SignalEvent
        import time
        rec = ev.recorder
        rec.record(SignalEvent(source="p", topic="polymarket.arb", payload={"edge": 0.05, "recommended_usd": 500}, priority=0))
        report = ev.evaluate(strategy="polymarket_arb", days=7)
        assert report.metrics.total == rec.get_signals(strategy="polymarket_arb", limit=10).__len__()

    def test_known_strategies(self):
        ev = StrategyEvaluator()
        # Initially empty DB = empty strategies
        strats = ev._known_strategies()
        assert isinstance(strats, list)

    def test_drawdown_calc(self):
        daily = [
            DailyStats(date="2024-01-01", signals_count=1, total_edge=0.05, avg_edge=0.05, max_edge=0.05, avg_size=500),
            DailyStats(date="2024-01-02", signals_count=1, total_edge=-0.03, avg_edge=-0.03, max_edge=-0.03, avg_size=500),
            DailyStats(date="2024-01-03", signals_count=1, total_edge=0.02, avg_edge=0.02, max_edge=0.02, avg_size=500),
        ]
        dd = StrategyEvaluator._calc_drawdown(daily)
        assert dd is not None
        assert dd >= 0.0

    def test_export_report(self, tmp_path):
        ev = StrategyEvaluator()
        from backtest.metrics import SignalMetrics
        from dataclasses import asdict
        report = ev.evaluate(strategy="test", days=1)
        path = ev.export_report(report, tmp_path / "test.json")
        assert path.exists()

    def test_evaluate_all(self):
        ev = StrategyEvaluator()
        reports = ev.evaluate_all(days=7)
        assert isinstance(reports, dict)
