"""
Backtest Metrics — обчислення показників ефективності стратегій.

Метрики:
    - total_signals, winning_signals, losing_signals
    - win_rate (%)
    - avg_edge, max_edge
    - sharpe_ratio (approximation для дискретних сигналів)
    - max_drawdown (%)
    - profit_factor
    - avg_recommended_size

Usage:
    from backtest.metrics import SignalMetrics, calculate_metrics
    signals = recorder.get_signals(strategy='polymarket_arb')
    metrics = calculate_metrics(signals)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, stdev
from typing import Sequence

from coordination.event_bus import SignalEvent


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SignalMetrics:
    """Метрики на основі набору сигналів."""
    total: int
    winning: int          # ті, де edge > 0 (потенційно прибуткові)
    losing: int
    win_rate: float       # 0..1
    avg_edge: float
    max_edge: float
    min_edge: float
    sharpe_ratio: float | None  # None якщо < 2 сигналів
    profit_factor: float | None  # None якщо немає losing
    avg_recommended_usd: float | None
    max_recommended_usd: float | None
    total_recommended_usd: float | None


# --------------------------------------------------------------------------- #
def _edges_and_sizes(signals: list):
    """Витягнути списки edge та recommended_usd."""
    edges = []
    sizes = []
    for s in signals:
        e = getattr(s, "edge", None)
        if e is not None and isinstance(e, (int, float)):
            edges.append(e)
        rec = getattr(s, "recommended_usd", None)
        if rec is not None and isinstance(rec, (int, float)):
            sizes.append(rec)
    return edges, sizes


def calculate_metrics(signals: Sequence) -> SignalMetrics:
    """Обчислити метрики для списку сигналів / RecordedSignal."""
    if not signals:
        return SignalMetrics(
            total=0,
            winning=0,
            losing=0,
            win_rate=0.0,
            avg_edge=0.0,
            max_edge=0.0,
            min_edge=0.0,
            sharpe_ratio=None,
            profit_factor=None,
            avg_recommended_usd=None,
            max_recommended_usd=None,
            total_recommended_usd=None,
        )

    edges, sizes = _edges_and_sizes(list(signals))
    n = len(signals)

    winning = sum(1 for e in edges if e > 0)
    losing = n - winning
    win_rate = winning / n if n else 0.0

    avg_edge = mean(edges) if edges else 0.0
    max_edge = max(edges) if edges else 0.0
    min_edge = min(edges) if edges else 0.0

    # Sharpe: mean / stdev (crude — для discrete signals edge ≈ return)
    sharpe = None
    if len(edges) >= 2:
        try:
            s = stdev(edges)
            sharpe = avg_edge / s if s > 0 else (avg_edge if avg_edge > 0 else -avg_edge)
        except Exception:
            pass

    # Profit factor: sum(winning edges) / abs(sum(losing edges))
    pf = None
    wins = [e for e in edges if e > 0]
    losses = [e for e in edges if e <= 0]
    if wins and losses:
        pf = abs(sum(wins) / sum(losses)) if sum(losses) != 0 else float("inf")
    elif wins:
        pf = float("inf")

    avg_usd = mean(sizes) if sizes else None
    max_usd = max(sizes) if sizes else None
    total_usd = sum(sizes) if sizes else None

    return SignalMetrics(
        total=n,
        winning=winning,
        losing=losing,
        win_rate=win_rate,
        avg_edge=avg_edge,
        max_edge=max_edge,
        min_edge=min_edge,
        sharpe_ratio=sharpe,
        profit_factor=pf,
        avg_recommended_usd=avg_usd,
        max_recommended_usd=max_usd,
        total_recommended_usd=total_usd,
    )
