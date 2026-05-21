"""
Scheduler Health Monitor — відстеження статусу cron job'ів.

Можливості:
    1. Запис last execution time per job
    2. Alert якщо job не виконувався > threshold
    3. Health check dashboard

Використання:
    from rooflow.health_monitor import HealthMonitor
    monitor = HealthMonitor()
    monitor.record_execution("english_daily_job", success=True)
    
    # Перевірка
    alerts = monitor.check_health()
    if alerts:
        send_telegram("\n".join(alerts), thread_id=25)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

HEALTH_FILE = Path(__file__).parent.parent / "data" / "scheduler_health.json"

# Job thresholds (hours without execution → alert)
DEFAULT_THRESHOLDS = {
    "english_daily_job": 26,       # Щодня → alert якщо > 26 год
    "crypto_report_job": 8,        # 3x на день → alert якщо > 8 год
    "fast_movers_job": 0.5,      # Кожні 5 хв → alert якщо > 30 хв
    "polymarket_scan_job": 1.0,    # Кожні 30 хв → alert якщо > 1 год
    "polymarket_depth_job": 3.0,   # Кожні 2 год → alert якщо > 3 год
    "polymarket_news_job": 8.0,    # Кожні 6 год → alert якщо > 8 год
    "polymarket_topic_job": 5.0,   # Кожні 4 год → alert якщо > 5 год
    "weekly_calibration_job": 170,   # Щотижня → alert якщо > 7 днів + 2 год
    "auto_sentiment_job": 8.0,     # Кожні 6 год
    "auto_prediction_job": 14.0,   # Кожні 12 год
    "dashboard_job": 1.0,          # Кожні 30 хв
}


@dataclass
class JobHealth:
    name: str
    last_run: str | None = None
    last_success: bool = True
    last_error: str | None = None
    total_runs: int = 0
    total_failures: int = 0
    threshold_hours: float = 24.0


class HealthMonitor:
    """Моніторинг здоров'я scheduler job'ів."""
    
    def __init__(self, health_file: Path | None = None):
        self.health_file = health_file or HEALTH_FILE
        self.health_file.parent.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, JobHealth] = {}
        self._load()
    
    def _load(self) -> None:
        """Завантажити історію з файлу."""
        if self.health_file.exists():
            try:
                data = json.loads(self.health_file.read_text(encoding="utf-8"))
                for name, info in data.items():
                    self.jobs[name] = JobHealth(
                        name=name,
                        last_run=info.get("last_run"),
                        last_success=info.get("last_success", True),
                        last_error=info.get("last_error"),
                        total_runs=info.get("total_runs", 0),
                        total_failures=info.get("total_failures", 0),
                        threshold_hours=info.get("threshold_hours", DEFAULT_THRESHOLDS.get(name, 24.0)),
                    )
            except (json.JSONDecodeError, KeyError) as e:
                log.warning("Failed to load health file: %s", e)
    
    def _save(self) -> None:
        """Зберегти історію в файл."""
        data = {
            name: {
                "last_run": job.last_run,
                "last_success": job.last_success,
                "last_error": job.last_error,
                "total_runs": job.total_runs,
                "total_failures": job.total_failures,
                "threshold_hours": job.threshold_hours,
            }
            for name, job in self.jobs.items()
        }
        self.health_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    def record_execution(self, job_name: str, success: bool = True, error: str | None = None) -> None:
        """Записати виконання job'у."""
        if job_name not in self.jobs:
            self.jobs[job_name] = JobHealth(
                name=job_name,
                threshold_hours=DEFAULT_THRESHOLDS.get(job_name, 24.0),
            )
        
        job = self.jobs[job_name]
        job.last_run = datetime.utcnow().isoformat()
        job.last_success = success
        job.last_error = error
        job.total_runs += 1
        if not success:
            job.total_failures += 1
        
        self._save()
        
        status = "✅" if success else "❌"
        log.info("%s Job %s executed (total: %d, failures: %d)", status, job_name, job.total_runs, job.total_failures)
    
    def check_health(self) -> list[str]:
        """
        Перевірити здоров'я всіх job'ів.
        
        Returns:
            List of alert strings (empty if all healthy)
        """
        alerts = []
        now = datetime.utcnow()
        
        for name, job in self.jobs.items():
            if job.last_run is None:
                alerts.append(f"⚠️ **{name}**: Never executed")
                continue
            
            last_run = datetime.fromisoformat(job.last_run)
            hours_since = (now - last_run).total_seconds() / 3600
            
            if hours_since > job.threshold_hours:
                if job.last_success:
                    alerts.append(
                        f"🔴 **{name}**: No execution for {hours_since:.1f}h "
                        f"(threshold: {job.threshold_hours:.1f}h)"
                    )
                else:
                    alerts.append(
                        f"🔴 **{name}**: FAILED + no retry for {hours_since:.1f}h "
                        f"(last error: {job.last_error or 'unknown'})"
                    )
            elif not job.last_success:
                alerts.append(
                    f"🟡 **{name}**: Last execution FAILED "
                    f"({hours_since:.1f}h ago: {job.last_error or 'unknown'})"
                )
        
        return alerts
    
    def get_status_table(self) -> list[dict]:
        """Отримати статус всіх job'ів для відображення."""
        now = datetime.utcnow()
        rows = []
        
        for name, job in self.jobs.items():
            if job.last_run:
                last_run = datetime.fromisoformat(job.last_run)
                hours_since = (now - last_run).total_seconds() / 3600
                status = "🔴" if hours_since > job.threshold_hours else ("🟡" if not job.last_success else "🟢")
                last = f"{hours_since:.1f}h ago"
            else:
                status = "⚪"
                last = "Never"
            
            rows.append({
                "job": name,
                "status": status,
                "last_run": last,
                "total": job.total_runs,
                "failures": job.total_failures,
                "threshold": f"{job.threshold_hours:.1f}h",
            })
        
        return rows
    
    def format_health_report(self) -> str:
        """Форматувати повний health report для Telegram."""
        alerts = self.check_health()
        status = self.get_status_table()
        
        lines = [
            f"🏥 **Scheduler Health Report**",
            f"_{datetime.utcnow().strftime('%H:%M UTC')}_",
            f"",
            f"**Jobs Monitored:** {len(status)}",
            f"",
        ]
        
        # Healthy vs unhealthy
        healthy = [s for s in status if s["status"] == "🟢"]
        warning = [s for s in status if s["status"] == "🟡"]
        critical = [s for s in status if s["status"] in ("🔴", "⚪")]
        
        lines.append(f"🟢 Healthy: {len(healthy)} | 🟡 Warning: {len(warning)} | 🔴 Critical: {len(critical)}")
        lines.append("")
        
        if alerts:
            lines.append(f"**Active Alerts:**")
            for alert in alerts:
                lines.append(f"  {alert}")
            lines.append("")
        
        lines.append(f"**Job Status:**")
        for s in status:
            lines.append(
                f"  {s['status']} {s['job'][:25]:25s} — {s['last_run']} "
                f"(runs: {s['total']}, fails: {s['failures']})"
            )
        
        return "\n".join(lines)
