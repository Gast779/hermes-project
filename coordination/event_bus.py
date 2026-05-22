"""
Event Bus — lightweight pub/sub для cross-agent комунікації.

Архітектура:
    1. SignalEvent — стандартний контейнер для подій між агентами.
    2. AgentBus — singleton pub/sub з SQLite persistence.
    3. Топіки: 'crypto.fast_mover', 'polymarket.arb', 'polymarket.news', 'system.health'
    4. Кожен агент може publish/subscribe без залежностей від інших.

Usage:
    from coordination.event_bus import SignalEvent, get_bus
    bus = get_bus()
    bus.subscribe('crypto.fast_mover', callback)
    bus.publish(SignalEvent(source='crypto_monitor', topic='crypto.fast_mover', payload={...}))
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Any

log = logging.getLogger(__name__)

DB_PATH = Path.home() / ".hermes" / "shared_event_log.db"


# --------------------------------------------------------------------------- #
@dataclass
class SignalEvent:
    """Стандартна подія між агентами."""
    source: str              # Назва агента-джерела (напр. 'crypto_monitor')
    topic: str               # Топік (напр. 'crypto.fast_mover')
    payload: dict[str, Any]  # Дані події
    priority: int = 0        # 0=info, 1=warning, 2=critical
    timestamp: float = field(default_factory=time.time)
    correlation_id: str | None = None  # ID для зв'язку між подіями

    def serialize(self) -> str:
        return json.dumps(asdict(self), default=str, ensure_ascii=False)

    @classmethod
    def deserialize(cls, raw: str) -> SignalEvent:
        data = json.loads(raw)
        return cls(
            source=data["source"],
            topic=data["topic"],
            payload=data["payload"],
            priority=data.get("priority", 0),
            timestamp=data.get("timestamp", time.time()),
            correlation_id=data.get("correlation_id"),
        )

    def is_critical(self) -> bool:
        return self.priority >= 2

    def __repr__(self) -> str:
        return f"SignalEvent({self.source}→{self.topic} p={self.priority})"


# --------------------------------------------------------------------------- #
EventHandler = Callable[[SignalEvent], None]


class AgentBus:
    """Потокобезпечний pub/sub для cross-agent комунікації."""

    _instance: AgentBus | None = None
    _lock = threading.Lock()

    def __new__(cls) -> AgentBus:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._subs: dict[str, list[EventHandler]] = {}
        self._sub_lock = threading.RLock()
        self._db_path = Path(DB_PATH)
        self._init_db()

    # -- DB -- #
    def _conn(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(self._db_path), check_same_thread=False)

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    source TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    payload TEXT NOT NULL,
                    correlation_id TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_topic_ts
                ON events(topic, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_correlation
                ON events(correlation_id)
            """)
            conn.commit()

    # -- Publish -- #
    def publish(self, event: SignalEvent) -> None:
        """Опублікувати подію: записує в БД і викликає всі callback'и."""
        payload_json = json.dumps(event.payload, default=str, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO events
                   (timestamp, source, topic, priority, payload, correlation_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event.timestamp, event.source, event.topic, event.priority,
                 payload_json, event.correlation_id),
            )
            conn.commit()
            _id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        log.info("[%s] event %s → %s (p=%s)", _id, event.source, event.topic, event.priority)

        with self._sub_lock:
            handlers = list(self._subs.get(event.topic, []))

        for h in handlers:
            try:
                h(event)
            except Exception:
                log.exception("Handler failed for %s", event.topic)

    # -- Subscribe -- #
    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Підписатися на топік."""
        with self._sub_lock:
            self._subs.setdefault(topic, []).append(handler)
        log.debug("Subscribed to %s", topic)

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        """Відписатися від топіку."""
        with self._sub_lock:
            handlers = self._subs.get(topic, [])
            if handler in handlers:
                handlers.remove(handler)

    # -- Query -- #
    def recent(self, topic: str | None = None, limit: int = 50) -> list[SignalEvent]:
        """Останні події (опціонально по топіку)."""
        with self._conn() as conn:
            if topic:
                rows = conn.execute(
                    """SELECT timestamp, source, topic, priority, payload, correlation_id
                       FROM events WHERE topic = ? ORDER BY timestamp DESC LIMIT ?""",
                    (topic, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT timestamp, source, topic, priority, payload, correlation_id
                       FROM events ORDER BY timestamp DESC LIMIT ?""",
                    (limit,),
                ).fetchall()

        events = []
        for ts, source, topic, prio, payload, corr in rows:
            assert topic is not None
            events.append(SignalEvent(
                source=source,
                topic=topic,
                priority=prio,
                payload=json.loads(payload),
                timestamp=ts,
                correlation_id=corr,
            ))
        return events

    def stats(self) -> dict[str, int]:
        """Кількість подій по топіках."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT topic, COUNT(*) FROM events GROUP BY topic"
            ).fetchall()
        return {topic: cnt for topic, cnt in rows}

    def prune(self, older_than_days: int = 30) -> int:
        """Видалити події старші за N днів."""
        cutoff = time.time() - older_than_days * 86400
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return cur.rowcount

# --------------------------------------------------------------------------- #
def get_bus() -> AgentBus:
    """Отримати singleton-інстанс AgentBus."""
    return AgentBus()
