"""Тести логіки FastMoversWatcher без виходу в мережу."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

from crypto_monitor.alerts import FastMoverAlert, FastMoversWatcher
from crypto_monitor.data_sources import CoinTicker


def _mock_cg(price_sequence):
    """Створює мок CoinGeckoClient, що повертає різні ціни на послідовні tick()."""
    cg = MagicMock()
    cg.get_top_markets.side_effect = price_sequence
    return cg


def _coin(coin_id: str, symbol: str, price: float) -> CoinTicker:
    return CoinTicker(
        id=coin_id, symbol=symbol, name=symbol,
        price_usd=price, market_cap_usd=10_000_000, total_volume_usd=2_000_000,
        pct_change_1h=None, pct_change_24h=None, pct_change_7d=None,
    )


def test_fast_5m_alert_fires():
    # Перший tick: 1.00; через 5 хв: 1.07 (+7%) → має спрацювати на ≥ 5%
    cg = _mock_cg([
        [_coin("test", "TST", 1.00)],
        [_coin("test", "TST", 1.07)],
    ])
    received = []
    w = FastMoversWatcher(cg, callback=received.append, pct_5m=5.0, pct_1h=20.0,
                          min_volume_24h=0, min_market_cap=0, cooldown_minutes=0)
    # Підкручуємо час вручну
    now = time.time()
    w._history["test"].append((now - 300, 1.00))    # 5 хв тому
    w._history["test"].append((now, 1.07))
    w._maybe_emit(_coin("test", "TST", 1.07), now)

    assert len(received) == 1
    a: FastMoverAlert = received[0]
    assert a.symbol == "TST"
    assert a.window == "5m"
    assert a.pct_change > 6.5


def test_1h_alert_overrides_5m():
    """Якщо обидва пороги перейдені — 1h-сигнал має пріоритет."""
    received = []
    w = FastMoversWatcher(MagicMock(), callback=received.append, pct_5m=5.0, pct_1h=20.0,
                          min_volume_24h=0, min_market_cap=0, cooldown_minutes=0)
    now = time.time()
    w._history["t"].append((now - 3600, 1.00))   # 1h тому
    w._history["t"].append((now - 300, 1.10))    # 5хв тому
    w._history["t"].append((now, 1.30))          # +18% за 5хв, +30% за 1h

    w._maybe_emit(_coin("t", "T", 1.30), now)

    assert len(received) == 1
    assert received[0].window == "1h"
    assert abs(received[0].pct_change - 30.0) < 1e-6


def test_cooldown_blocks_repeats():
    received = []
    w = FastMoversWatcher(MagicMock(), callback=received.append, pct_5m=5.0, pct_1h=20.0,
                          min_volume_24h=0, min_market_cap=0, cooldown_minutes=30)
    now = time.time()
    w._cooldown["t"] = now - 60     # 1 хв тому
    w._history["t"].append((now - 300, 1.00))
    w._history["t"].append((now, 1.10))

    w._maybe_emit(_coin("t", "T", 1.10), now)
    assert received == []


def test_volume_filter_blocks_thin_coins():
    received = []
    w = FastMoversWatcher(MagicMock(), callback=received.append, pct_5m=5.0, pct_1h=20.0,
                          min_volume_24h=1_000_000, min_market_cap=0, cooldown_minutes=0)
    now = time.time()
    w._history["scam"].append((now - 300, 1.00))
    w._history["scam"].append((now, 1.10))

    thin = CoinTicker(id="scam", symbol="SCM", name="Scam",
                      price_usd=1.10, market_cap_usd=0, total_volume_usd=100,  # < 1M
                      pct_change_1h=None, pct_change_24h=None, pct_change_7d=None)
    w._maybe_emit(thin, now)
    assert received == []
