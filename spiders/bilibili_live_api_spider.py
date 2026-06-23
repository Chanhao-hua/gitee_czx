from __future__ import annotations

import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import requests

try:
    from spiders.bootstrap import ensure_project_root_on_path
except ModuleNotFoundError:
    from bootstrap import ensure_project_root_on_path


ensure_project_root_on_path()

from app.cleaning import filter_bilibili_live
from app.config import DEFAULT_TARGET_RECORDS, GAME_PARENT_AREA_IDS, MAX_WORKERS, SOURCE_TIMEOUT_SECONDS
from spiders.common import write_dataset


AREA_LIST_URL = "https://api.live.bilibili.com/xlive/web-interface/v1/index/getWebAreaList"
ROOM_LIST_URL = "https://api.live.bilibili.com/room/v3/area/getRoomList"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://live.bilibili.com/",
}


@dataclass
class BilibiliLiveArea:
    area_id: int
    parent_area_id: int
    parent_area_name: str
    area_name: str
    room_id: int
    room_title: str
    streamer_name: str
    online: int
    tags: str
    cover_url: str
    room_url: str


def fetch_live_rankings(
    limit_per_area: int = 1,
    limit: int | None = None,
    workers: int = MAX_WORKERS,
) -> list[BilibiliLiveArea]:
    session = _session()
    area_response = session.get(
        AREA_LIST_URL,
        params={"source_id": 2},
        timeout=SOURCE_TIMEOUT_SECONDS,
    )
    area_response.raise_for_status()
    areas = area_response.json()["data"]["data"]

    jobs: list[tuple[int, str, int, str]] = []
    for parent in areas:
        parent_id = int(parent["id"])
        if parent_id not in GAME_PARENT_AREA_IDS:
            continue
        parent_name = parent["name"]
        for child in parent.get("list", []):
            area_id = int(child["id"])
            if area_id != 0:
                jobs.append((parent_id, parent_name, area_id, child["name"]))

    raw_records: list[dict] = []
    executor = ThreadPoolExecutor(max_workers=max(1, min(workers, MAX_WORKERS)))
    futures = [
        executor.submit(_fetch_room_page, parent_id, parent_name, area_id, area_name, limit_per_area)
        for parent_id, parent_name, area_id, area_name in jobs
    ]
    try:
        for future in as_completed(futures):
            try:
                raw_records.extend(future.result())
            except requests.RequestException:
                continue
            if limit:
                raw_records = filter_bilibili_live(raw_records, limit=limit)
                if len(raw_records) >= limit:
                    for pending in futures:
                        pending.cancel()
                    break
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    raw_records = filter_bilibili_live(raw_records, limit=limit)
    raw_records.sort(key=lambda item: int(item["online"]), reverse=True)
    return [BilibiliLiveArea(**record) for record in raw_records]


def main() -> None:
    args = _parse_args("Bilibili live API spider")
    started_at = time.perf_counter()
    raw_records = [
        item.__dict__
        for item in fetch_live_rankings(limit_per_area=8, limit=args.limit, workers=args.workers)
    ]
    cleaned_records = filter_bilibili_live(raw_records, limit=args.limit)
    write_dataset("bilibili_api_live", raw_records, cleaned_records, started_at)


def _parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--limit", type=int, default=DEFAULT_TARGET_RECORDS, help="target record count")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="parallel request workers")
    return parser.parse_args()


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _fetch_room_page(parent_id: int, parent_name: str, area_id: int, area_name: str, limit_per_area: int) -> list[dict]:
    response = _session().get(
        ROOM_LIST_URL,
        params={
            "platform": "web",
            "parent_area_id": parent_id,
            "area_id": area_id,
            "page": 1,
            "page_size": max(1, min(limit_per_area, 30)),
        },
        timeout=(4, 10),
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        return []
    records = []
    for item in payload["data"].get("list", [])[:limit_per_area]:
        room_id = int(item["roomid"])
        records.append(
            {
                "area_id": area_id,
                "parent_area_id": parent_id,
                "parent_area_name": parent_name,
                "area_name": area_name,
                "room_id": room_id,
                "room_title": item.get("title", "").strip(),
                "streamer_name": item.get("uname", "").strip(),
                "online": int(item.get("online", 0)),
                "tags": item.get("tags", "").strip(),
                "cover_url": item.get("user_cover", "").strip(),
                "room_url": f"https://live.bilibili.com/{room_id}",
            }
        )
    return records


if __name__ == "__main__":
    main()
