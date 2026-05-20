"""
SQLite-сховище для історії алертів і арбітражних можливостей.

Чому це потрібно:
    1. Аналіз false-positive rate (скільки наших сигналів реально були
       прибутковими).
    2. Дедуплікація (cooldown в памʼяті губиться при рестарті).
    3. Бектести: чи мав сенс сигнал по BTC від 14:32, якщо подивитись
       на ціну через годину.

Схема:
    crypto_alerts(id, coin_id, symbol, price, window, pct, ts_utc, ...)
    arb_opportunities(id, market_id, slug, kind, edge, ts_utc, json_payload)
    news_links(id, news_url, market_slug, score, ts_utc)

Один файл .db за замовчуванням у ~/.hermes/state.db — переноситься між машинами.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_DB = Path("~/.hermes/state.db").expanduser()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS crypto_alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc      TEXT    NOT NULL,
    coin_id     TEXT    NOT NULL,
    symbol      TEXT    NOT NULL,
    name        TEXT,
    price_usd   REAL    NOT NULL,
    window      TEXT    NOT NULL,      -- '5m' | '1h'
    pct_change  REAL    NOT NULL,
    volume_24h  REAL,
    market_cap  REAL
);
CREATE INDEX IF NOT EXISTS ix_crypto_alerts_coin_ts ON crypto_alerts(coin_id, ts_utc);

CREATE TABLE IF NOT EXISTS arb_opportunities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc      TEXT    NOT NULL,
    market_id   TEXT    NOT NULL,
    slug        TEXT    NOT NULL,
    question    TEXT,
    kind        TEXT    NOT NULL,
    edge        REAL    NOT NULL,
    sum_asks    REAL,
    sum_bids    REAL,
    volume_usd  REAL,
    payload     TEXT                  -- raw JSON для дебагу
);
CREATE INDEX IF NOT EXISTS ix_arb_market_ts ON arb_opportunities(market_id, ts_utc);

CREATE TABLE IF NOT EXISTS news_links (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc       TEXT    NOT NULL,
    news_title   TEXT    NOT NULL,
    news_url     TEXT    NOT NULL,
    news_source  TEXT,
    market_slug  TEXT    NOT NULL,
    market_id    TEXT,
    score        REAL    NOT NULL,
    UNIQUE(news_url, market_id)
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, path: Path | str = DEFAULT_DB):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ---- crypto alerts --------------------------------------------------- #
    def save_alert(self, alert: Any) -> int:
        cur = self._conn.execute(
            """INSERT INTO crypto_alerts
               (ts_utc, coin_id, symbol, name, price_usd, window, pct_change, volume_24h, market_cap)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _now_iso(),
                alert.coin_id, alert.symbol, alert.name, alert.price,
                alert.window, alert.pct_change,
                getattr(alert, "volume_24h", None),
                getattr(alert, "market_cap", None),
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def recent_alerts(self, coin_id: str | None = None, limit: int = 50) -> list[sqlite3.Row]:
        if coin_id:
            q = "SELECT * FROM crypto_alerts WHERE coin_id=? ORDER BY ts_utc DESC LIMIT ?"
            return list(self._conn.execute(q, (coin_id, limit)))
        return list(self._conn.execute(
            "SELECT * FROM crypto_alerts ORDER BY ts_utc DESC LIMIT ?", (limit,)))

    def was_alerted_recently(self, coin_id: str, since_seconds: int) -> bool:
        """Перевіряє чи був алерт по цій монеті за останні N секунд (persistent cooldown)."""
        cutoff = datetime.now(timezone.utc).timestamp() - since_seconds
        row = self._conn.execute(
            "SELECT ts_utc FROM crypto_alerts WHERE coin_id=? ORDER BY ts_utc DESC LIMIT 1",
            (coin_id,),
        ).fetchone()
        if not row:
            return False
        try:
            ts = datetime.fromisoformat(row["ts_utc"]).timestamp()
        except ValueError:
            return False
        return ts >= cutoff

    # ---- arbitrage ------------------------------------------------------- #
    def save_arb(self, opp: Any) -> int:
        payload = json.dumps(asdict(opp) if hasattr(opp, "__dataclass_fields__") else opp)
        cur = self._conn.execute(
            """INSERT INTO arb_opportunities
               (ts_utc, market_id, slug, question, kind, edge, sum_asks, sum_bids, volume_usd, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _now_iso(), opp.market_id, opp.slug, opp.question, opp.kind,
                opp.edge, opp.sum_asks, opp.sum_bids, opp.volume_usd, payload,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def recent_arb(self, limit: int = 30) -> list[sqlite3.Row]:
        return list(self._conn.execute(
            "SELECT * FROM arb_opportunities ORDER BY ts_utc DESC LIMIT ?", (limit,)))

    # ---- news links ------------------------------------------------------ #
    def save_news_link(self, news_url: str, news_title: str, news_source: str,
                       market_slug: str, market_id: str, score: float) -> bool:
        try:
            self._conn.execute(
                """INSERT INTO news_links (ts_utc, news_title, news_url, news_source,
                                            market_slug, market_id, score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (_now_iso(), news_title, news_url, news_source, market_slug, market_id, score),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            # UNIQUE(news_url, market_id) — уже записували
            return False

    # ---- utility --------------------------------------------------------- #
    def stats(self) -> dict[str, int]:
        c = self._conn.execute("SELECT COUNT(*) FROM crypto_alerts").fetchone()[0]
        a = self._conn.execute("SELECT COUNT(*) FROM arb_opportunities").fetchone()[0]
        n = self._conn.execute("SELECT COUNT(*) FROM news_links").fetchone()[0]
        return {"crypto_alerts": c, "arb_opportunities": a, "news_links": n}

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
