from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from .cleaning import filter_bilibili_live, filter_static_games
from .config import CLEANED_DATA_DIR, DEFAULT_TARGET_RECORDS, MAX_WORKERS, RAW_DATA_DIR
from .utils import utc_now_iso
from spiders.bilibili_dynamic_live_spider import fetch_dynamic_live_rooms
from spiders.bilibili_live_api_spider import fetch_live_rankings
from spiders.static_game_spider import fetch_static_games


DATASET_SPECS = {
    "static_game_catalog": {
        "label": "静态网页源",
        "key": "source_url",
        "required": ["name", "source_url"],
    },
    "bilibili_api_live": {
        "label": "API 接口源",
        "key": "room_id",
        "required": ["room_title", "room_url"],
    },
    "bilibili_dynamic_live": {
        "label": "动态页面源",
        "key": "room_id",
        "required": ["room_title", "room_url"],
    },
}


def refresh_batch_sources(limit: int = DEFAULT_TARGET_RECORDS) -> dict:
    started_at = time.perf_counter()
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    CLEANED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    datasets = []
    errors = []
    for name, fetcher, cleaner in [
        ("static_game_catalog", _fetch_static, _clean_static),
        ("bilibili_api_live", _fetch_api, filter_bilibili_live),
        ("bilibili_dynamic_live", _fetch_dynamic, filter_bilibili_live),
    ]:
        source_started = time.perf_counter()
        try:
            raw_records = fetcher(limit)
            cleaned_records = cleaner(raw_records, limit=limit)
            _write_json(RAW_DATA_DIR / f"{name}.json", raw_records)
            _write_json(CLEANED_DATA_DIR / f"{name}.json", cleaned_records)
            datasets.append(
                {
                    "name": name,
                    "label": DATASET_SPECS[name]["label"],
                    "raw_count": len(raw_records),
                    "cleaned_count": len(cleaned_records),
                    "elapsed_seconds": round(time.perf_counter() - source_started, 2),
                    "cleaned_path": str(CLEANED_DATA_DIR / f"{name}.json"),
                }
            )
        except Exception as exc:
            errors.append({"name": name, "error": str(exc)})

    return {
        "started": True,
        "message": "自动爬取完成" if not errors else "部分数据源爬取失败",
        "limit": limit,
        "datasets": datasets,
        "errors": errors,
        "finished_at": utc_now_iso(),
        "elapsed_seconds": round(time.perf_counter() - started_at, 2),
    }


def get_batch_status() -> dict:
    datasets = []
    for name, spec in DATASET_SPECS.items():
        path = CLEANED_DATA_DIR / f"{name}.json"
        count = 0
        updated_at = None
        if path.exists():
            try:
                count = len(json.loads(path.read_text(encoding="utf-8")))
                updated_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime))
            except json.JSONDecodeError:
                count = 0
        datasets.append(
            {
                "name": name,
                "label": spec["label"],
                "count": count,
                "updated_at": updated_at,
                "path": str(path),
            }
        )
    return {"datasets": datasets, "generated_at": utc_now_iso()}


def load_cleaned_dataset(name: str) -> list[dict]:
    path = CLEANED_DATA_DIR / f"{name}.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _fetch_static(limit: int) -> list[dict]:
    return [asdict(item) for item in fetch_static_games(limit=limit)]


def _fetch_api(limit: int) -> list[dict]:
    return [asdict(item) for item in fetch_live_rankings(limit_per_area=8, limit=limit, workers=MAX_WORKERS)]


def _fetch_dynamic(limit: int) -> list[dict]:
    return fetch_dynamic_live_rooms(limit, workers=MAX_WORKERS)


def _clean_static(records: list[dict], limit: int) -> list[dict]:
    return filter_static_games(records, limit=limit)


def _write_json(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
