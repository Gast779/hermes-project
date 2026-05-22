"""
Backtest Recorder — запис подій з Event Bus для подальшої оцінки.

Зберігає:
    - timestamp, source, topic, payload
    - event bus events (arb, fast_mover)
    - signals (arb: edge, market, sizing)

Usage:
    from backtest.recorder import BacktestRecorder, get_recorder
    rec = get_recorder()
    rec.start_recording()  # auto-subscribe to relevant topics

    # Later:
    signals = rec.get_signals(strategy='polymarket_arb')
    signals = rec.get_signals(topic='crypto.fast_mover')
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from coordination.event_bus import SignalEvent

log = logging.getLogger(__name__)

DB_PATH = Path.home() / ".hermes" / "backtest_log.db"


# --------------------------------------------------------------------------- #
@dataclass
class RecordedSignal:
    """Записаний сигнал для backtest."""
    id: int | None
    timestamp: float
    source: str              # агент-джерело
    topic: str
    strategy: str | None     # 'polymarket_arb', 'crypto_fast_mover'
    payload: dict[str, Any]
    
    # Extracted fields (для зручності):
    edge: float | None = None
    recommended_usd: float | None = None
    symbol: str | None = None
    pct_change: float | None = None


# --------------------------------------------------------------------------- #
class BacktestRecorder:
    """Запис подій Event Bus для backtest / аналізу."""

    _instance: BacktestRecorder | None = None

    def __new__(cls) -> BacktestRecorder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._db_path = Path(DB_PATH)
        self._init_db()
        self._handler: Callable | None = None  # stored for unsubscribe

    # -- DB -- #
    def _conn(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(self._db_path), check_same_thread=False)

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    source TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    strategy TEXT,
                    payload TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_topic_ts
                ON backtest_signals(topic, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_strategy
                ON backtest_signals(strategy, timestamp)
            """)
            conn.commit()

    # -- Recording -- #
    def record(self, event: SignalEvent) -> int:
        """Записати SignalEvent у БД."""
        strategy = self._infer_strategy(event)
        payload_json = json.dumps(event.payload, default=str, ensure_ascii=False)
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO backtest_signals
                   (timestamp, source, topic, strategy, payload)
                   VALUES (?, ?, ?, ?, ?)""",
                (event.timestamp, event.source, event.topic, strategy, payload_json),
            )
            conn.commit()
            return cur.lastrowid or 0

    def _infer_strategy(self, event: SignalEvent) -> str | None:
        """Визначити стратегію за топіком."""
        if event.topic == "polymarket.arb":
            return "polymarket_arb"
        if event.topic == "crypto.fast_mover":
            return "crypto_fast_mover"
        return None

    def _on_event(self, event: SignalEvent) -> None:
        """Handler для Event Bus."""
        _id = self.record(event)
        log.debug("Recorded signal %s: %s/%s", _id, event.source, event.topic)

    def start_recording(self) -> None:
        """Підписатися на Event Bus і почати запис."""
        from coordination.event_bus import get_bus
        bus = get_bus()
        self._handler = self._on_event
        bus.subscribe("polymarket.arb", self._handler)
        bus.subscribe("crypto.fast_mover", self._handler)
        log.info("BacktestRecorder started")

    def stop_recording(self) -> None:
        """Відписатися від Event Bus."""
        if self._handler is None:
            return
        from coordination.event_bus import get_bus
        bus = get_bus()
        bus.unsubscribe("polymarket.arb", self._handler)
        bus.unsubscribe("crypto.fast_mover", self._handler)
        log.info("BacktestRecorder stopped")

    # -- Query -- #
    def get_signals(
        self,
        *,
        topic: str | None = None,
        strategy: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 10000,
    ) -> list[RecordedSignal]:
        """Отримати записані сигнали."""
        conditions = []
        params: list[Any] = []

        if topic:
            conditions.append("topic = ?")
            params.append(topic)
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("timestamp <= ?")
            params.append(until)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT id, timestamp, source, topic, strategy, payload
                    FROM backtest_signals
                    {where}
                    ORDER BY timestamp DESC
                    LIMIT ?""",
                params + [limit],
            ).fetchall()

        signals = []
        for row in rows:
            payload = json.loads(row[5])
            sig = RecordedSignal(
                id=row[0],
                timestamp=row[1],
                source=row[2],
                topic=row[3],
                strategy=row[4],
                payload=payload,
                edge=payload.get("edge"),
                recommended_usd=payload.get("recommended_usd"),
                symbol=payload.get("symbol"),
                pct_change=payload.get("pct_change"),
            )
            signals.append(sig)
        return signals

    def count(self) -> int:
        """Кількість записаних сигналів."""
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM backtest_signals").fetchone()
            return row[0] if row else 0

    def prune(self, older_than_days: int = 90) -> int:
        """Видалити записи старші за N днів."""
        cutoff = time.time() - older_than_days * 86400
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM backtest_signals WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return cur.rowcount

    def export_csv(self, path: Path | None = None) -> Path:
        """Експортувати у CSV."""
        import csv
        path = path or self._db_path.parent / f"backtest_export_{datetime.now():%Y%m%d_%H%M}.csv"
        signals = self.get_signals(limit=1000000)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "timestamp", "source", "topic", "strategy", "edge", "symbol", "pct_change"])
            for s in signals:
                writer.writerow([s.id, s.timestamp, s.source, s.topic, s.strategy,
                                 s.edge, s.symbol, s.pct_change])
        return path


# --------------------------------------------------------------------------- #
def get_recorder() -> BacktestRecorder:
    return BacktestRecorder()
