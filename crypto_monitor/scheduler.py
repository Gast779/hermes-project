"""
APScheduler-обгортка: будує scheduler з усіма cron-задачами.
"""
from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)


def build_scheduler(timezone: str = "Europe/Kyiv") -> BlockingScheduler:
    return BlockingScheduler(timezone=timezone)


def add_cron_job(
    scheduler: BlockingScheduler,
    job: Callable,
    cron_expr: str,
    *,
    name: str | None = None,
) -> None:
    """
    cron_expr приклади:
        "0 9 * * *"     — щодня о 09:00
        "*/15 * * * *"  — кожні 15 хв
    """
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr!r}")
    minute, hour, day, month, day_of_week = parts
    trigger = CronTrigger(
        minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week,
        timezone=scheduler.timezone,
    )
    scheduler.add_job(job, trigger, name=name or job.__name__, replace_existing=True)
    log.info("Scheduled %s (%s)", name or job.__name__, cron_expr)
