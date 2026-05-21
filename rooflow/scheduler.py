"""
RooFlow Scheduler — інтеграція APScheduler з RooFlow Engine.

Кожен cron job:
    1. Перемикає агента в відповідний режим (code/ask/debug)
    2. Логує start в executionLog
    3. Виконує job
    4. Логує результат / помилку
    5. При помилці → режим debug
"""
from __future__ import annotations

import functools
import logging
from datetime import datetime
from typing import Callable

from rooflow.engine import RooFlowEngine

log = logging.getLogger(__name__)


AGENT_MAP: dict[str, str] = {
    "crypto-report": "crypto_monitor",
    "polymarket-scan": "polymarket_analyzer",
    "english-daily": "english_bot",
    "english-lesson": "english_bot",
}


def rooflow_wrap(job_fn: Callable, agent: str, mode: str = "code") -> Callable:
    """
    Обгортає job-функцію в RooFlow instrumentation.
    
    Args:
        job_fn: Оригінальна функція job
        agent: Ім'я агента (english_bot | crypto_monitor | polymarket_analyzer)
        mode: Режим перед виконанням (code — для звітів, ask — для пояснень)
    
    Returns:
        Обгорнута функція з автоматичним логуванням
    """
    engine = RooFlowEngine()

    @functools.wraps(job_fn)
    def _wrapped() -> None:
        job_name = getattr(job_fn, "__name__", "unknown")
        
        # 1. Перемкнути режим
        original_mode = engine.get_mode(agent)
        if original_mode != mode:
            engine.switch_mode(agent, mode, reason=f"Scheduled job: {job_name}")
        
        # 2. Логувати старт
        engine._log_execution(agent, mode, f"🚀 Job start: {job_name}")
        
        start_time = datetime.utcnow()
        try:
            # 3. Виконати job
            result = job_fn()
            
            # 4. Успіх — логувати результат
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            engine._log_execution(agent, mode, f"✅ Job done: {job_name} ({elapsed:.1f}s)")
            
        except Exception as exc:
            # 5. Помилка — логувати та перейти в debug
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"❌ Job failed: {job_name} ({elapsed:.1f}s) — {type(exc).__name__}: {exc}"
            engine._log_execution(agent, "debug", error_msg)
            engine.switch_mode(agent, "debug", reason=f"Job error: {type(exc).__name__}")
            
            # Запис в decisionLog
            engine.append_memory_bank(
                agent, "decisionLog.md",
                f"\n- **{datetime.utcnow().isoformat()[:19]}** — Job error: {job_name}\n"
                f"  - Помилка: `{type(exc).__name__}: {exc}`\n"
                f"  - Дія: Перемкнено в debug режим\n"
                f"  - Результат: Потрібно виправити перед наступним запуском\n"
            )
            raise
        
        finally:
            # 6. Повернути режим, якщо він змінився
            current = engine.get_mode(agent)
            if current == mode and original_mode != mode and original_mode != "debug":
                engine.switch_mode(agent, original_mode, reason=f"Job {job_name} completed")
    
    return _wrapped


def build_rooflow_scheduler(scheduler, jobs_config: list[dict]) -> None:
    """
    Додає всі job'и в scheduler з RooFlow instrumentation.
    
    Args:
        scheduler: APScheduler instance
        jobs_config: Список job-конфігів:
            [
                {"job": crypto_report_job, "cron": "0 9 * * *", "agent": "crypto_monitor", "mode": "code"},
                ...
            ]
    """
    from crypto_monitor.scheduler import add_cron_job
    
    for cfg in jobs_config:
        job_fn = cfg["job"]
        agent = cfg.get("agent", "unknown")
        mode = cfg.get("mode", "code")
        cron = cfg["cron"]
        name = cfg.get("name", job_fn.__name__)
        
        wrapped = rooflow_wrap(job_fn, agent, mode)
        add_cron_job(scheduler, wrapped, cron, name=f"{name}")
        log.info("Registered RooFlow job: %s (%s) → %s mode=%s", name, cron, agent, mode)
