"""
Telegram Dashboard — періодична відправка RooFlow статусу в Telegram.

Запускається: кожні 30 хвилин (cron: */30 * * * *)
Результат: Форматований dashboard → Telegram DM або група

Формат:
    ┌─────────────────────────────────────┐
    │ 🤖 Hermes RooFlow Dashboard          │
    │ 14:30 UTC | 4 agents active          │
    ├─────────────────────────────────────┤
    │ english_bot      💻 code             │
    │ crypto_monitor   ❓ ask               │
    │ polymarket_anal. ❓ ask               │
    │ mirofish        🏗️ architect          │
    ├─────────────────────────────────────┤
    │ Handoffs: 0 active | 5 completed      │
    │ Predictions: 3 active | 2 resolved    │
    │ Avg Brier: 0.1423 🥈                 │
    ├─────────────────────────────────────┤
    │ 📋 Next Jobs:                         │
    │ • 14:35 Fast Movers                  │
    │ • 15:00 PM Arbitrage                 │
    │ • 16:00 Deep Scan                    │
    └─────────────────────────────────────┘
"""
from __future__ import annotations

import logging
from datetime import datetime

from rooflow.engine import RooFlowEngine
from scripts.notify_telegram import send_telegram

log = logging.getLogger(__name__)


def send_dashboard(chat_id: str = "-1003792129186", thread_id: int | None = None) -> dict:
    """
    Згенерувати та відправити RooFlow dashboard в Telegram.
    
    Args:
        chat_id: Telegram chat ID (default: Hermes_team group)
        thread_id: Topic thread ID (None для DM)
    """
    engine = RooFlowEngine()
    data = engine.dashboard()
    
    # Форматувати повідомлення
    now = datetime.utcnow().strftime("%H:%M UTC")
    
    lines = [
        f"🤖 **Hermes RooFlow Dashboard**",
        f"_{now} | {len(data['agents'])} agents active_",
        f"",
        f"**Agent Status:**",
    ]
    
    # Emoji для режимів
    mode_emoji = {
        "architect": "🏗️",
        "code": "💻",
        "debug": "🐛",
        "ask": "❓",
        "orchestrate": "🎭",
    }
    
    for agent, info in data["agents"].items():
        emoji = mode_emoji.get(info["mode"], "❓")
        mode = info["mode"]
        history = info["history_count"]
        lines.append(f"  {emoji} {agent:20s} {mode} ({history} switches)")
    
    # Handoffs
    lines.append(f"")
    lines.append(f"**Handoffs:**")
    # Парсимо handoffs.md для статистики
    handoffs_content = engine.read_shared("handoffs.md")
    active_count = handoffs_content.count("🟡")
    completed_count = handoffs_content.count("🟢")
    lines.append(f"  🔴 Active: {active_count} | 🟢 Completed: {completed_count}")
    
    # Predictions
    stats = engine.get_prediction_stats()
    if stats["total"] > 0:
        lines.append(f"")
        lines.append(f"**Predictions:**")
        lines.append(f"  🟢 Active: {stats['active']} | ⚫ Resolved: {stats['resolved']}")
        if stats["avg_brier"] is not None:
            # Grade
            brier = stats["avg_brier"]
            if brier <= 0.05:
                grade = "🥇"
            elif brier <= 0.15:
                grade = "🥈"
            elif brier <= 0.25:
                grade = "🥉"
            else:
                grade = "⚠️"
            lines.append(f"  Avg Brier: {brier:.4f} {grade}")
    
    # Shared Memory
    lines.append(f"")
    lines.append(f"**Memory Bank:**")
    for fname, size in data["shared_files"].items():
        lines.append(f"  📄 {fname}: {size:,} bytes")
    
    # Footer
    lines.append(f"")
    lines.append(f"_Commands: rooflow status | rooflow predictions | rooflow workflows_")
    
    message = "\n".join(lines)
    
    # Відправити
    send_telegram(
        message,
        chat_id=chat_id,
        message_thread_id=thread_id,
    )
    
    log.info("Dashboard sent to %s", chat_id)
    
    return {
        "status": "sent",
        "agents": len(data["agents"]),
        "timestamp": now,
    }
