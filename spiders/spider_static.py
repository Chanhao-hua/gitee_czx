from __future__ import annotations

import time

from app.cleaning import filter_static_games
from app.crawlers.gamersky_static import fetch_static_games
from spiders.common import parse_limit, write_dataset


def main() -> None:
    args = parse_limit("Steam static search crawler")
    started_at = time.perf_counter()
    raw_records = [item.__dict__ for item in fetch_static_games(limit=args.limit)]
    cleaned_records = filter_static_games(raw_records, limit=args.limit)
    write_dataset("static_game_catalog", raw_records, cleaned_records, started_at)


if __name__ == "__main__":
    main()
