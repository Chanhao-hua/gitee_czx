from __future__ import annotations

import time
import argparse

try:
    from spiders.bootstrap import ensure_project_root_on_path
except ModuleNotFoundError:
    from bootstrap import ensure_project_root_on_path


ensure_project_root_on_path()

from app.cleaning import filter_bilibili_live
from spiders.bilibili_live_api_spider import fetch_live_rankings
from app.config import DEFAULT_TARGET_RECORDS, MAX_WORKERS
from spiders.common import write_dataset


def fetch_dynamic_live_rooms(limit: int, workers: int = MAX_WORKERS) -> list[dict]:
    return [
        item.__dict__
        for item in fetch_live_rankings(limit_per_area=8, limit=limit, workers=workers)
    ]


def main() -> None:
    args = _parse_args("Bilibili dynamic live room spider")
    started_at = time.perf_counter()
    raw_records = fetch_dynamic_live_rooms(args.limit, workers=args.workers)
    cleaned_records = filter_bilibili_live(raw_records, limit=args.limit)
    write_dataset("bilibili_dynamic_live", raw_records, cleaned_records, started_at)


def _parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--limit", type=int, default=DEFAULT_TARGET_RECORDS, help="target record count")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="parallel request workers")
    return parser.parse_args()


if __name__ == "__main__":
    main()
