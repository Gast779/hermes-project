"""
Backtest Evaluator — оцінка стратегій за історичними сигналами.

Робить:
    1. Бере сигнали з recorder.
    2. Групує за стратегі / днем / тижнем.
    3. Рахує метрики: win_rate, sharpe, drawdown, profit_factor.
    4. Генерує звіт з порівняння стратегій.

Usage:
    from backtest.evaluator import StrategyEvaluator, get_evaluator
    ev = get_evaluator()
    report = ev.evaluate(strategy='polymarket_arb', days=30)
    # або
    report = ev.evaluate_all(days=7)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from coordination.event_bus import SignalEvent

from .metrics import SignalMetrics, calculate_metrics
from .recorder import BacktestRecorder, RecordedSignal, get_recorder

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
@dataclass
class DailyStats:
    date: str
    signals_count: int
    total_edge: float
    avg_edge: float
    max_edge: float
    avg_size: float | None


@dataclass
class StrategyReport:
    strategy: str
    period_days: int
    since: str
    until: str
    metrics: SignalMetrics
    daily: list[DailyStats]
    # Risk-adjusted
    drawdown: float | None    # макс. drawdown від максимальної edge


# --------------------------------------------------------------------------- #
class StrategyEvaluator:
    """Оцінює стратегію за історичними сигналами."""

    _instance: StrategyEvaluator | None = None

    def __new__(cls) -> StrategyEvaluator:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self.recorder = get_recorder()

    def evaluate(
        self,
        *,
        strategy: str,
        days: int = 30,
    ) -> StrategyReport:
        """Оцінити одну стратегію за останні N днів."""
        since = time.time() - days * 86400
        signals = self.recorder.get_signals(strategy=strategy, since=since, limit=100000)
        metrics = calculate_metrics(signals)

        # Daily stats
        daily_map: dict[str, list[RecordedSignal]] = {}
        for s in signals:
            date = datetime.fromtimestamp(s.timestamp).strftime("%Y-%m-%d")
            daily_map.setdefault(date, []).append(s)
        daily = []
        for date, day_signals in sorted(daily_map.items()):
            dm = calculate_metrics(day_signals)
            daily.append(DailyStats(
                date=date,
                signals_count=dm.total,
                total_edge=sum(getattr(s, "edge", 0) or 0 for s in day_signals),
                avg_edge=dm.avg_edge,
                max_edge=dm.max_edge,
                avg_size=dm.avg_recommended_usd,
            ))

        # Drawdown: max peak-to-trough of daily total_edge
        drawdown = self._calc_drawdown(daily)

        return StrategyReport(
            strategy=strategy,
            period_days=days,
            since=datetime.fromtimestamp(since).isoformat(),
            until=datetime.now().isoformat(),
            metrics=metrics,
            daily=daily,
            drawdown=drawdown,
        )

    def evaluate_all(self, *, days: int = 30) -> dict[str, StrategyReport]:
        """Оцінити всі відомі стратегії."""
        strategies = self._known_strategies()
        return {s: self.evaluate(strategy=s, days=days) for s in strategies}

    def _known_strategies(self) -> list[str]:
        """Взнати які стратегії є в БД."""
        with self.recorder._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT strategy FROM backtest_signals WHERE strategy IS NOT NULL"
            ).fetchall()
        return sorted([r[0] for r in rows])

    @staticmethod
    def _calc_drawdown(daily: Sequence[DailyStats]) -> float | None:
        """Макс. drawdown як % від cumulative edge."""
        if not daily:
            return None
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for d in daily:
            cumulative += d.total_edge
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd

    def export_report(self, report: StrategyReport, path: Path | None = None) -> Path:
        """Експортувати звіт у JSON."""
        path = path or Path.home() / ".hermes" / f"backtest_{report.strategy}_{datetime.now():%Y%m%d}.json"
        data = {
            "strategy": report.strategy,
            "period_days": report.period_days,
            "since": report.since,
            "until": report.until,
            "metrics": asdict(report.metrics),
            "drawdown": report.drawdown,
            "daily": [asdict(d) for d in report.daily],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return path


def get_evaluator() -> StrategyEvaluator:
    return StrategyEvaluator()
