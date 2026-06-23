from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from .config import REFRESH_INTERVAL_MINUTES
from .services import CrawlService


def create_scheduler(crawl_service: CrawlService) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        crawl_service.refresh_all,
        "interval",
        minutes=REFRESH_INTERVAL_MINUTES,
        id="refresh-all-sources",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
