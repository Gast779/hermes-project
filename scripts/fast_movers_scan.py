#!/usr/bin/env python3
"""
Одноразовий скан fast-movers для cron (не daemon).
Використовує FastMoversWatcher.tick() один раз і виходить.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from crypto_monitor import CoinGeckoClient, FastMoversWatcher
from crypto_monitor.alerts import FastMoverAlert

def format_alert(a: FastMoverAlert) -> str:
    emoji = "🚀" if a.pct_change > 0 else "📉"
    return (
        f"{emoji} **{a.symbol}** {a.name}\n"
        f"   Зміна: {a.pct_change:+.2f}% за {a.window}\n"
        f"   Ціна: ${a.price:.4f}\n"
        f"   Обʼєм 24h: ${a.volume_24h:,.0f}\n"
        f"   [CoinGecko]({a.chart_url})"
    )

def main():
    cg = CoinGeckoClient()
    alerts: list[str] = []

    def callback(a: FastMoverAlert):
        alerts.append(format_alert(a))

    watcher = FastMoversWatcher(
        cg=cg,
        callback=callback,
        pct_5m=5.0,
        pct_1h=20.0,
        poll_interval_seconds=60,
    )

    # Один тик — перевіряємо рухи
    n = watcher.tick()

    if alerts:
        print("🚀 **Fast Movers Alert**\n")
        print("\n\n".join(alerts))
        print(f"\n_Виявлено {len(alerts)} сигнал(ів)_")
    else:
        print("🟢 Fast Movers: різких рухів не виявлено.")

    return 0 if not alerts else 1  # 1 = були алерти

if __name__ == "__main__":
    sys.exit(main())
