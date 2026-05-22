"""
Auto-pause механізми коли система веде себе ненормально.

Активуються автоматично, потребують manual override щоб reset.
"""
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional


class BreakerStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    TRIPPED = "tripped"      # auto-pause active
    MANUAL_OVERRIDE = "override"


@dataclass
class Breaker:
    name: str
    description: str
    threshold: float
    current_value: float
    status: BreakerStatus
    tripped_at: Optional[datetime] = None
    auto_reset_after: Optional[timedelta] = None


CIRCUIT_BREAKERS_DB = Path.home() / ".hermes" / "circuit_breakers.db"


def init_breakers_db():
    conn = sqlite3.connect(CIRCUIT_BREAKERS_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS breaker_state (
            name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            current_value REAL,
            threshold REAL,
            tripped_at TEXT,
            auto_reset_at TEXT,
            override_by TEXT,
            override_at TEXT,
            metadata TEXT
        );

        CREATE TABLE IF NOT EXISTS breaker_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            breaker_name TEXT,
            event_type TEXT,  -- tripped, reset, override
            timestamp TEXT,
            details TEXT
        );
    """)
    conn.commit()
    conn.close()


# ─── Breaker checks ─────────────────────────────────────────────────
def check_daily_loss(daily_pnl_pct: float) -> Breaker:
    """Daily loss > 5% → freeze."""
    return Breaker(
        name="daily_loss_5pct",
        description="Daily loss exceeds 5% of bankroll",
        threshold=-0.05,
        current_value=daily_pnl_pct,
        status=BreakerStatus.TRIPPED if daily_pnl_pct < -0.05 else
               BreakerStatus.WARNING if daily_pnl_pct < -0.03 else
               BreakerStatus.OK,
        auto_reset_after=timedelta(hours=24),
    )


def check_drawdown(peak_bankroll: float, current_bankroll: float) -> Breaker:
    """Drawdown > 20% від peak → emergency stop."""
    drawdown = (peak_bankroll - current_bankroll) / peak_bankroll if peak_bankroll > 0 else 0
    return Breaker(
        name="drawdown_20pct",
        description="Total drawdown from peak exceeds 20%",
        threshold=0.20,
        current_value=drawdown,
        status=BreakerStatus.TRIPPED if drawdown > 0.20 else
               BreakerStatus.WARNING if drawdown > 0.10 else
               BreakerStatus.OK,
        auto_reset_after=None,  # потребує manual review
    )


def check_consecutive_losses(losses_in_row: int) -> Breaker:
    """5+ losses поспіль в одній стратегії → pause strategy."""
    return Breaker(
        name="consecutive_losses",
        description="Too many consecutive losses",
        threshold=5,
        current_value=losses_in_row,
        status=BreakerStatus.TRIPPED if losses_in_row >= 5 else
               BreakerStatus.WARNING if losses_in_row >= 3 else
               BreakerStatus.OK,
        auto_reset_after=timedelta(hours=12),
    )


def check_api_error_rate(error_rate_pct: float, sample_size: int) -> Breaker:
    """>20% API failures за 1h → pause integrations."""
    return Breaker(
        name="api_errors",
        description="API error rate too high",
        threshold=0.20,
        current_value=error_rate_pct,
        status=BreakerStatus.TRIPPED if error_rate_pct > 0.20 and sample_size > 10 else
               BreakerStatus.WARNING if error_rate_pct > 0.10 and sample_size > 5 else
               BreakerStatus.OK,
        auto_reset_after=timedelta(minutes=30),
    )


def check_price_anomaly(price: float, recent_median: float, recent_std: float) -> Breaker:
    """Price > 5 sigma від recent median → likely API glitch чи маніпуляція."""
    if recent_std == 0:
        return Breaker("price_anomaly", "n/a", 5, 0, BreakerStatus.OK)
    sigmas = abs(price - recent_median) / recent_std
    return Breaker(
        name="price_anomaly_5sigma",
        description="Price diverges > 5 sigma from recent median",
        threshold=5.0,
        current_value=sigmas,
        status=BreakerStatus.TRIPPED if sigmas > 5 else
               BreakerStatus.WARNING if sigmas > 3 else
               BreakerStatus.OK,
        auto_reset_after=timedelta(minutes=10),
    )


# ─── Master check ───────────────────────────────────────────────────
def check_all_breakers(state: dict) -> dict:
    """
    Запускає всі breakers, повертає statuses.
    state — dict з усіма потрібними метриками.
    """
    breakers = [
        check_daily_loss(state.get("daily_pnl_pct", 0)),
        check_drawdown(state.get("peak_bankroll", 1), state.get("current_bankroll", 1)),
        check_consecutive_losses(state.get("losses_in_row", 0)),
        check_api_error_rate(state.get("api_error_rate", 0), state.get("api_calls", 0)),
    ]

    persist_breakers(breakers)

    return {
        "all_ok": all(b.status == BreakerStatus.OK for b in breakers),
        "any_tripped": any(b.status == BreakerStatus.TRIPPED for b in breakers),
        "tripped": [b.name for b in breakers if b.status == BreakerStatus.TRIPPED],
        "warnings": [b.name for b in breakers if b.status == BreakerStatus.WARNING],
        "details": {b.name: b.__dict__ for b in breakers},
    }


def persist_breakers(breakers: list) -> None:
    """Зберігає state breakers у DB для моніторингу."""
    conn = sqlite3.connect(CIRCUIT_BREAKERS_DB)
    for b in breakers:
        conn.execute("""
            INSERT INTO breaker_state (name, status, current_value, threshold, tripped_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                status=excluded.status,
                current_value=excluded.current_value,
                tripped_at=CASE
                    WHEN excluded.status = 'tripped' THEN COALESCE(breaker_state.tripped_at, excluded.tripped_at)
                    ELSE NULL
                    END
        """, (
            b.name, b.status.value, b.current_value, b.threshold,
            datetime.utcnow().isoformat() if b.status == BreakerStatus.TRIPPED else None,
        ))
    conn.commit()
    conn.close()


def trading_allowed() -> tuple[bool, list[str]]:
    """
    Простий публічний API. Викликати ПЕРЕД будь-яким trade signal.

    Returns:
        (allowed, list_of_tripped_breakers)
    """
    conn = sqlite3.connect(CIRCUIT_BREAKERS_DB)
    rows = conn.execute(
        "SELECT name FROM breaker_state WHERE status = 'tripped'"
    ).fetchall()
    conn.close()
    tripped = [r[0] for r in rows]
    return (len(tripped) == 0, tripped)
