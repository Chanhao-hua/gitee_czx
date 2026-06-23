from __future__ import annotations

import time

from app.cleaning import filter_bilibili_live
from app.crawlers.bilibili_live import fetch_live_rankings
from spiders.common import parse_limit, write_dataset


def main() -> None:
    args = parse_limit("Bilibili dynamic live room crawler")
    started_at = time.perf_counter()
    raw_records = [item.__dict__ for item in fetch_live_rankings(limit_per_area=8, limit=args.limit)]
    cleaned_records = filter_bilibili_live(raw_records, limit=args.limit)
    write_dataset("bilibili_dynamic_live", raw_records, cleaned_records, started_at)


if __name__ == "__main__":
    main()
