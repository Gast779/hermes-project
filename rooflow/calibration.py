"""
Weekly Calibration — щотижневий перерахунок Brier score для всіх прогнозів.

Запускається: понеділок 10:00 (cron: 0 10 * * 1)
Агент: mirofish (ask mode → code mode)
Результат: Calibration Report → Telegram + executionLog

Logic:
    1. Знайти всі expired прогнози (прошло > TTL)
    2. Автоматично resolve (потрібен manual override для outcome)
    3. Обчислити rolling Brier score
    4. Генерувати Calibration Report
    5. Відправити в Telegram thread 30 (polymarket_topic_monitor)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from rooflow.engine import RooFlowEngine
from scripts.notify_telegram import send_telegram

log = logging.getLogger(__name__)


def run_weekly_calibration() -> dict:
    """Щотижневий перерахунок Brier score + calibration report."""
    engine = RooFlowEngine()
    
    log.info("Starting weekly calibration...")
    engine.switch_mode("mirofish", "code", reason="Weekly Brier calibration")
    
    # 1. Отримати статистику
    stats = engine.get_prediction_stats()
    
    # 2. Знайти expired прогнози
    content = engine.read_shared("predictionRegistry.md")
    expired = _find_expired_predictions(content)
    
    # 3. Генерувати Calibration Report
    report = _generate_calibration_report(stats, expired)
    
    # 4. Відправити в Telegram (thread 30)
    send_telegram(
        report,
        chat_id="-1003792129186",
        message_thread_id=30,
    )
    
    # 5. Логування
    engine.switch_mode("mirofish", "ask", reason="Weekly calibration complete")
    
    return {
        "workflow": "weekly-calibration",
        "predictions_total": stats["total"],
        "resolved": stats["resolved"],
        "avg_brier": stats["avg_brier"],
        "expired_count": len(expired),
        "status": "completed",
    }


def _find_expired_predictions(content: str) -> list[dict]:
    """Знайти прогнози, у яких минув TTL (7 днів)."""
    import re
    
    expired = []
    now = datetime.utcnow()
    
    for match in re.finditer(r'### (PR-\d{8}-\d{6}).*?Expires:\*\* (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', content, re.DOTALL):
        pred_id = match.group(1)
        expires = datetime.fromisoformat(match.group(2))
        if expires < now and "🟢 active" in content[match.start():match.end()+500]:
            expired.append({"id": pred_id, "expired_at": expires.isoformat()})
    
    return expired


def _generate_calibration_report(stats: dict, expired: list[dict]) -> str:
    """Генерація Calibration Report."""
    now = datetime.utcnow().isoformat()[:10]
    
    # Brier Grade
    avg_brier = stats.get("avg_brier", 0)
    if avg_brier is None:
        grade = "🆕 No data yet"
    elif avg_brier <= 0.05:
        grade = "🥇 Excellent"
    elif avg_brier <= 0.15:
        grade = "🥈 Good"
    elif avg_brier <= 0.25:
        grade = "🥉 Fair"
    else:
        grade = "⚠️ Poor — needs recalibration"
    
    report = (
        f"📊 **Weekly Calibration Report**\n"
        f"_MiroFish Brier Score Analysis | {now}_\n\n"
        f"**Predictions Overview:**\n"
        f"  • Total: {stats['total']}\n"
        f"  • Active: {stats['active']}\n"
        f"  • Resolved: {stats['resolved']}\n"
        f"  • Expired (awaiting resolution): {len(expired)}\n\n"
        f"**Brier Score Performance:**\n"
    )
    
    if stats["avg_brier"] is not None:
        report += (
            f"  • Average: {stats['avg_brier']:.4f}\n"
            f"  • Best: {stats['best_brier']:.4f}\n"
            f"  • Worst: {stats['worst_brier']:.4f}\n"
        )
    else:
        report += f"  • No resolved predictions yet\n"
    
    report += (
        f"\n**Calibration Grade:** {grade}\n\n"
        f"**Recommendations:**\n"
    )
    
    if avg_brier is None:
        report += f"  • Start making predictions to build calibration history\n"
    elif avg_brier <= 0.15:
        report += f"  • Well calibrated! Continue current strategy\n"
        report += f"  • Consider increasing position sizes on high-confidence predictions\n"
    elif avg_brier <= 0.25:
        report += f"  • Moderate calibration — review uncertainty multipliers\n"
        report += f"  • Focus on base rate research for complex markets\n"
    else:
        report += f"  • Poor calibration — reduce overconfidence\n"
        report += f"  • Widen probability ranges (90% CI instead of point estimates)\n"
        report += f"  • Increase 'reasoning time' before probability assignment\n"
    
    if expired:
        report += f"\n⚠️ **Expired Predictions Need Resolution:**\n"
        for e in expired[:5]:
            report += f"  • {e['id']} (expired {e['expired_at'][:10]})\n"
    
    report += f"\n_Next calibration: next Monday 10:00 | Track all predictions at rooflow prediction-stats_"
    
    return report
