from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from ..cleaning import filter_steam_details, filter_steam_popular
from ..config import DEFAULT_TARGET_RECORDS, MAX_WORKERS, SOURCE_TIMEOUT_SECONDS
from ..utils import collapse_list


STEAM_SEARCH_URL = "https://store.steampowered.com/search/"
STEAM_SEARCH_RESULTS_URL = "https://store.steampowered.com/search/results/"
STEAM_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
STEAM_PAGE_SIZE = 50
STEAM_SEARCH_SEEDS = [
    {"filter": "popularnew", "category1": "998"},
    {"term": "a", "category1": "998"},
    {"term": "e", "category1": "998"},
    {"term": "i", "category1": "998"},
    {"term": "o", "category1": "998"},
    {"term": "r", "category1": "998"},
    {"term": "s", "category1": "998"},
    {"term": "t", "category1": "998"},
    {"term": "game", "category1": "998"},
    {"term": "the", "category1": "998"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


@dataclass
class SteamPopularGame:
    app_id: int
    rank_index: int
    name: str
    release_date: str
    discount_text: str
    final_price: str
    review_summary: str
    platforms: str
    source_url: str


@dataclass
class SteamGameDetail:
    app_id: int
    name: str
    is_free: bool
    developers: str
    publishers: str
    genres: str
    categories: str
    supported_languages: str
    short_description: str
    header_image: str
    detail_url: str


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def fetch_popular_new(limit: int = DEFAULT_TARGET_RECORDS, workers: int = 8) -> list[SteamPopularGame]:
    page_count = max(1, (limit // STEAM_PAGE_SIZE) + 2)
    jobs = [
        (seed, start, seed_index * page_count + page_index)
        for seed_index, seed in enumerate(STEAM_SEARCH_SEEDS)
        for page_index, start in enumerate(range(0, page_count * STEAM_PAGE_SIZE, STEAM_PAGE_SIZE))
    ]
    raw_records: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, MAX_WORKERS))) as executor:
        futures = {
            executor.submit(_fetch_popular_page, seed, start, page_index): (seed, start)
            for seed, start, page_index in jobs
        }
        for future in as_completed(futures):
            try:
                raw_records.extend(future.result())
            except requests.RequestException:
                continue
            raw_records = filter_steam_popular(raw_records, limit=limit)
            if len(raw_records) >= limit:
                break
    raw_records.sort(key=lambda item: int(item["rank_index"]))
    return [SteamPopularGame(**record) for record in raw_records[:limit]]


def fetch_app_details(app_ids: Iterable[int], workers: int = 12, limit: int | None = None) -> list[SteamGameDetail]:
    unique_app_ids = []
    seen: set[int] = set()
    for app_id in app_ids:
        app_id = int(app_id)
        if app_id in seen:
            continue
        seen.add(app_id)
        unique_app_ids.append(app_id)
        if limit and len(unique_app_ids) >= limit:
            break

    raw_records: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, MAX_WORKERS))) as executor:
        futures = {executor.submit(_fetch_app_detail, app_id): app_id for app_id in unique_app_ids}
        for future in as_completed(futures):
            record = future.result()
            if record:
                raw_records.append(record)

    raw_records = filter_steam_details(raw_records, limit=limit)
    raw_records.sort(key=lambda item: unique_app_ids.index(int(item["app_id"])) if int(item["app_id"]) in unique_app_ids else 999999)
    return [SteamGameDetail(**record) for record in raw_records]


def _fetch_popular_page(seed: dict, start: int, page_index: int) -> list[dict]:
    params = {**seed, "start": start, "count": STEAM_PAGE_SIZE}
    session = _session()
    response = session.get(STEAM_SEARCH_URL, params=params, timeout=SOURCE_TIMEOUT_SECONDS)
    if response.status_code != 200 or "search_result_row" not in response.text:
        response = session.get(
            STEAM_SEARCH_RESULTS_URL,
            params={**params, "infinite": 1},
            timeout=SOURCE_TIMEOUT_SECONDS,
        )
    response.raise_for_status()
    text = _extract_search_html(response)
    soup = BeautifulSoup(text, "html.parser")
    rows = soup.select("#search_resultsRows a.search_result_row")
    records: list[dict] = []
    for offset, row in enumerate(rows, start=1):
        href = row.get("href", "").strip()
        app_id = _extract_app_id(href)
        if not app_id:
            continue
        title = row.select_one("span.title")
        release = row.select_one("div.search_released")
        review = row.select_one("span.search_review_summary")
        price = row.select_one("div.discount_final_price")
        discount = row.select_one("div.discount_pct")
        platforms = _extract_platforms(row)
        records.append(
            {
                "app_id": app_id,
                "rank_index": page_index * STEAM_PAGE_SIZE + offset,
                "name": title.get_text(strip=True) if title else "",
                "release_date": release.get_text(" ", strip=True) if release else "",
                "discount_text": discount.get_text(strip=True) if discount else "",
                "final_price": price.get_text(" ", strip=True) if price else "",
                "review_summary": review.get("data-tooltip-html", "").replace("<br>", " ").strip() if review else "",
                "platforms": collapse_list(platforms),
                "source_url": href,
            }
        )
    return records


def _extract_search_html(response: requests.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return response.text
    payload = response.json()
    return payload.get("results_html", "")


def _fetch_app_detail(app_id: int) -> dict | None:
    response = _session().get(
        STEAM_APPDETAILS_URL,
        params={"appids": app_id, "l": "schinese"},
        timeout=SOURCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    raw = payload.get(str(app_id), {})
    if not raw.get("success"):
        return None
    app = raw["data"]
    return {
        "app_id": app_id,
        "name": app.get("name", ""),
        "is_free": bool(app.get("is_free", False)),
        "developers": collapse_list(app.get("developers", [])),
        "publishers": collapse_list(app.get("publishers", [])),
        "genres": collapse_list([item.get("description", "") for item in app.get("genres", [])]),
        "categories": collapse_list([item.get("description", "") for item in app.get("categories", [])]),
        "supported_languages": app.get("supported_languages", "").replace("<br>", " ").replace("<strong>*</strong>", "").strip(),
        "short_description": app.get("short_description", "").strip(),
        "header_image": app.get("header_image", ""),
        "detail_url": f"https://store.steampowered.com/app/{app_id}/",
    }


def _extract_platforms(row) -> list[str]:
    platforms = []
    for span in row.select("div.search_platforms span.platform_img"):
        classes = " ".join(span.get("class", []))
        if "win" in classes:
            platforms.append("Windows")
        if "mac" in classes:
            platforms.append("macOS")
        if "linux" in classes:
            platforms.append("Linux")
    return platforms


def _extract_app_id(href: str) -> int | None:
    parts = [part for part in href.split("/") if part]
    for idx, part in enumerate(parts):
        if part == "app" and idx + 1 < len(parts):
            candidate = parts[idx + 1]
            if candidate.isdigit():
                return int(candidate)
    return None
