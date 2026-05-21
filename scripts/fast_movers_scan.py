#!/usr/bin/env python3
"""
Одноразовий скан fast-movers для cron (не daemon).
Використовує FastMoversWatcher.tick() один раз і виходить.
Надсилає алерти в Telegram thread 26 (crypto_fast_movers).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from crypto_monitor import CoinGeckoClient, FastMoversWatcher
from crypto_monitor.alerts import FastMoverAlert
from scripts.notify_telegram import send_telegram

# Telegram topic для fast movers
FAST_MOVERS_THREAD_ID = 26
FAST_MOVERS_CHAT_ID = "-1003792129186"

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
        header = "🚀 **Fast Movers Alert**\n\n"
        body = "\n\n".join(alerts)
        footer = f"\n\n_Виявлено {len(alerts)} сигнал(ів)_"
        full_message = header + body + footer
        
        # Відправити в Telegram
        send_telegram(
            full_message,
            chat_id=FAST_MOVERS_CHAT_ID,
            message_thread_id=FAST_MOVERS_THREAD_ID,
        )
        
        print(full_message)
    else:
        print("🟢 Fast Movers: різких рухів не виявлено.")

    return 0 if not alerts else 1  # 1 = були алерти

if __name__ == "__main__":
    sys.exit(main())
