"""Backtest Framework: record, evaluate, analyze historical signals."""

from .recorder import BacktestRecorder, RecordedSignal, get_recorder
from .metrics import SignalMetrics, calculate_metrics
from .evaluator import StrategyEvaluator, StrategyReport, DailyStats, get_evaluator

__all__ = [
    "BacktestRecorder", "RecordedSignal", "get_recorder",
    "SignalMetrics", "calculate_metrics",
    "StrategyEvaluator", "StrategyReport", "DailyStats", "get_evaluator",
]