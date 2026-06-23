from __future__ import annotations

import threading
from dataclasses import asdict

from .batch_crawl import load_cleaned_dataset, refresh_batch_sources
from .config import DEFAULT_TARGET_RECORDS
from .crawlers.bilibili_video import fetch_strategy_videos, fetch_strategy_videos_bulk
from .repository import begin_run, finish_run, replace_bilibili_live, replace_steam_popular
from .utils import utc_now_iso


class CrawlService:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def refresh_all(self) -> dict:
        if not self._lock.acquire(blocking=False):
            return {"started": False, "message": "已有爬取任务正在运行"}
        try:
            result = refresh_batch_sources(DEFAULT_TARGET_RECORDS)
            self._refresh_dashboard_tables()
            return result
        finally:
            self._lock.release()

    def _refresh_dashboard_tables(self) -> None:
        static_run_id = begin_run("static_game_catalog")
        try:
            static_records = [
                {**item, "app_id": index, "rank_index": index, "scraped_at": utc_now_iso()}
                for index, item in enumerate(
                    load_cleaned_dataset("static_game_catalog")[:DEFAULT_TARGET_RECORDS],
                    start=1,
                )
            ]
            replace_steam_popular(static_records)
            finish_run(static_run_id, "success", len(static_records))
        except Exception as exc:
            finish_run(static_run_id, "failed", 0, str(exc))

        live_run_id = begin_run("bilibili_live_api")
        try:
            live_records = _top_live_room_per_area(load_cleaned_dataset("bilibili_api_live"))
            replace_bilibili_live(live_records)
            finish_run(live_run_id, "success", len(live_records))
        except Exception as exc:
            finish_run(live_run_id, "failed", 0, str(exc))


def find_strategy_videos(game_name: str) -> list[dict]:
    return [
        {**asdict(item), "scraped_at": utc_now_iso()}
        for item in fetch_strategy_videos(game_name)
    ]


def find_strategy_videos_for_games(game_names: list[str], limit: int = DEFAULT_TARGET_RECORDS) -> list[dict]:
    return [
        {**asdict(item), "scraped_at": utc_now_iso()}
        for item in fetch_strategy_videos_bulk(game_names, limit=limit)
    ]


def _top_live_room_per_area(records: list[dict]) -> list[dict]:
    best_by_area: dict[int, dict] = {}
    for item in records:
        area_id = int(item.get("area_id") or 0)
        if not area_id:
            continue
        current = best_by_area.get(area_id)
        if current is None or int(item.get("online") or 0) > int(current.get("online") or 0):
            best_by_area[area_id] = {**item, "scraped_at": utc_now_iso()}
    return sorted(best_by_area.values(), key=lambda item: int(item.get("online") or 0), reverse=True)
