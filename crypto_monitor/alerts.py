"""
Real-time детектор сильних рухів.

Логіка:
    1. Кожні N секунд (за замовчуванням 60s) тягнемо top-N монет з CoinGecko.
    2. Зберігаємо історію цін у словнику {coin_id: [(ts, price), ...]}.
    3. Рахуємо % зміни за 5хв і 1год.
    4. Якщо перевищено поріг — викликаємо callback (Telegram / лог / Hermes).
    5. Cooldown: не повторюємо алерт по тій самій монеті частіше за X хвилин.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable, Deque

from .data_sources import CoinGeckoClient, CoinTicker

log = logging.getLogger(__name__)


@dataclass
class FastMoverAlert:
    coin_id: str
    symbol: str
    name: str
    price: float
    window: str           # "5m" | "1h"
    pct_change: float
    volume_24h: float
    market_cap: float
    timestamp: float = field(default_factory=time.time)

    @property
    def chart_url(self) -> str:
        return f"https://www.coingecko.com/en/coins/{self.coin_id}"


AlertCallback = Callable[[FastMoverAlert], None]


class FastMoversWatcher:
    """Поточний рунер, який можна запустити як background-thread або з scheduler-у."""

    def __init__(
        self,
        cg: CoinGeckoClient,
        callback: AlertCallback,
        *,
        pct_5m: float = 5.0,
        pct_1h: float = 20.0,
        poll_interval_seconds: int = 60,
        min_volume_24h: float = 500_000,
        min_market_cap: float = 1_000_000,
        cooldown_minutes: int = 30,
        track_top_n: int = 200,
    ):
        self.cg = cg
        self.callback = callback
        self.pct_5m = pct_5m
        self.pct_1h = pct_1h
        self.poll_interval = poll_interval_seconds
        self.min_volume_24h = min_volume_24h
        self.min_market_cap = min_market_cap
        self.cooldown_seconds = cooldown_minutes * 60
        self.track_top_n = track_top_n

        # price_history[coin_id] = deque[(timestamp, price)]
        self._history: dict[str, Deque[tuple[float, float]]] = defaultdict(lambda: deque(maxlen=200))
        # cooldown[coin_id] = last alert ts
        self._cooldown: dict[str, float] = {}
        self._stop = False

    # ------------------------------------------------------------------ #
    def stop(self) -> None:
        self._stop = True

    def _record(self, c: CoinTicker, ts: float) -> None:
        self._history[c.id].append((ts, c.price_usd))

    def _pct_change_over(self, coin_id: str, seconds: int, now: float) -> float | None:
        """Скільки % зміни ціни за останні `seconds`."""
        hist = self._history.get(coin_id)
        if not hist or len(hist) < 2:
            return None
        target_ts = now - seconds
        # Знаходимо найстаріший запис, який ≥ (now - seconds - tolerance)
        # Tolerance = 30% від вікна — щоб точки могли бути неточно вирівняні.
        tolerance = seconds * 0.3
        old_price: float | None = None
        for ts, price in hist:
            if ts >= target_ts - tolerance:
                old_price = price
                break
        if old_price is None or old_price == 0:
            return None
        latest_price = hist[-1][1]
        return (latest_price - old_price) / old_price * 100.0

    def _maybe_emit(self, c: CoinTicker, now: float) -> None:
        # cooldown
        last = self._cooldown.get(c.id, 0)
        if now - last < self.cooldown_seconds:
            return

        # фільтри якості
        if c.total_volume_usd < self.min_volume_24h:
            return
        if c.market_cap_usd < self.min_market_cap:
            return

        pct5 = self._pct_change_over(c.id, 5 * 60, now)
        pct1h = self._pct_change_over(c.id, 60 * 60, now)

        alert: FastMoverAlert | None = None
        if pct5 is not None and pct5 >= self.pct_5m:
            alert = FastMoverAlert(c.id, c.symbol, c.name, c.price_usd, "5m", pct5,
                                   c.total_volume_usd, c.market_cap_usd)
        if pct1h is not None and pct1h >= self.pct_1h:
            # 1h-сигнал важливіший — перезаписуємо
            alert = FastMoverAlert(c.id, c.symbol, c.name, c.price_usd, "1h", pct1h,
                                   c.total_volume_usd, c.market_cap_usd)

        if alert:
            self._cooldown[c.id] = now
            try:
                self.callback(alert)
            except Exception as e:    # noqa: BLE001
                log.exception("Alert callback failed: %s", e)

    # ------------------------------------------------------------------ #
    def tick(self) -> int:
        """Один обхід API. Повертає кількість сигналів."""
        now = time.time()
        # Тягнемо track_top_n (≤250 за одну сторінку CoinGecko)
        per_page = min(self.track_top_n, 250)
        coins = self.cg.get_top_markets(per_page=per_page, page=1, price_change="1h,24h")
        emitted = 0
        for c in coins:
            self._record(c, now)
            before = len(self._cooldown)
            self._maybe_emit(c, now)
            after = len(self._cooldown)
            emitted += (after > before)
        return emitted

    def run_forever(self) -> None:
        log.info(
            "FastMoversWatcher starting (top %s, %s%% / 5m, %s%% / 1h, interval %ss)",
            self.track_top_n, self.pct_5m, self.pct_1h, self.poll_interval
        )
        while not self._stop:
            try:
                n = self.tick()
                if n:
                    log.info("Emitted %s alerts.", n)
            except Exception as e:    # noqa: BLE001
                log.exception("Tick error: %s", e)
            time.sleep(self.poll_interval)
