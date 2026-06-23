from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from spiders.bootstrap import ensure_project_root_on_path
except ModuleNotFoundError:
    from bootstrap import ensure_project_root_on_path


ensure_project_root_on_path()

from app.cleaning import filter_static_games
from app.config import DEFAULT_TARGET_RECORDS, SOURCE_TIMEOUT_SECONDS
from spiders.common import parse_limit, write_dataset


GAMERSKY_URL = "https://ku.gamersky.com/"
STEAM_SEARCH_URL = "https://store.steampowered.com/search/results/"
STEAM_PAGE_SIZE = 100
STEAM_SEARCHES = [
    {"filter": "topsellers"},
    {"filter": "globaltopsellers"},
    {"filter": "popularnew"},
    {"filter": "specials"},
    {"filter": "newreleases"},
    {"filter": "comingsoon"},
    {"sort_by": "Released_DESC", "category1": "998"},
    {"sort_by": "Reviews_DESC", "category1": "998"},
    {"sort_by": "Name_ASC", "category1": "998"},
]


@dataclass
class StaticGameInfo:
    app_id: int
    rank_index: int
    name: str
    platforms: str
    source_url: str
    header_image: str
    source_site: str


def fetch_static_games(limit: int = DEFAULT_TARGET_RECORDS) -> list[StaticGameInfo]:
    records = _safe_fetch_gamersky()
    records = filter_static_games(records, limit=limit)
    if len(records) < limit:
        records.extend(_fetch_steam_games(records, limit))

    records = filter_static_games(records, limit=limit)
    for index, record in enumerate(records, start=1):
        record["app_id"] = int(record.get("app_id") or index)
        record["rank_index"] = index
    return [StaticGameInfo(**record) for record in records[:limit]]


def main() -> None:
    args = parse_limit("Static game catalog spider")
    started_at = time.perf_counter()
    raw_records = [item.__dict__ for item in fetch_static_games(limit=args.limit)]
    cleaned_records = filter_static_games(raw_records, limit=args.limit)
    write_dataset("static_game_catalog", raw_records, cleaned_records, started_at)


def _safe_fetch_gamersky() -> list[dict]:
    try:
        return _fetch_gamersky()
    except requests.RequestException:
        return []


def _fetch_gamersky() -> list[dict]:
    response = requests.get(
        GAMERSKY_URL,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=SOURCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")

    records = []
    for index, item in enumerate(soup.select("li.gamelist"), start=1):
        link = item.select_one("a[href]")
        image = item.select_one("img")
        title = item.select_one("p")
        if not link or not title:
            continue
        game_id = item.get("gameid") or index
        records.append(
            _record(
                app_id=int(game_id) if str(game_id).isdigit() else index,
                name=title.get_text(" ", strip=True),
                source_url=urljoin(GAMERSKY_URL, link.get("href", "")),
                header_image=urljoin(GAMERSKY_URL, image.get("src", "")) if image else "",
                source_site="游民星空游戏库",
            )
        )
    return records


def _fetch_steam_games(seed_records: list[dict], limit: int) -> list[dict]:
    records = []
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"})

    for search in STEAM_SEARCHES:
        for start in range(0, limit + STEAM_PAGE_SIZE, STEAM_PAGE_SIZE):
            try:
                results_html = _fetch_steam_search_page(session, search, start)
            except (requests.RequestException, ValueError):
                break
            records.extend(_parse_steam_results(results_html))
            cleaned_count = len(filter_static_games([*seed_records, *records], limit=limit))
            if cleaned_count >= limit or not results_html:
                return records
    return records


def _fetch_steam_search_page(session: requests.Session, search: dict[str, str], start: int) -> str:
    params = {
        **search,
        "start": start,
        "count": STEAM_PAGE_SIZE,
        "infinite": 1,
        "cc": "cn",
        "l": "schinese",
    }
    response = session.get(STEAM_SEARCH_URL, params=params, timeout=SOURCE_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json().get("results_html", "")


def _parse_steam_results(results_html: str) -> list[dict]:
    soup = BeautifulSoup(results_html, "html.parser")
    records = []
    for item in soup.select("a.search_result_row"):
        app_id = item.get("data-ds-appid", "").split(",")[0]
        title = item.select_one(".title")
        image = item.select_one("img")
        href = _strip_query(item.get("href", ""))
        if not app_id.isdigit() or not title or not href:
            continue
        records.append(
            _record(
                app_id=int(app_id),
                name=title.get_text(" ", strip=True),
                source_url=href,
                header_image=image.get("src", "") if image else "",
                source_site="Steam 商店热销榜",
            )
        )
    return records


def _strip_query(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl()


def _record(app_id: int, name: str, source_url: str, header_image: str, source_site: str) -> dict:
    return {
        "app_id": app_id,
        "rank_index": 0,
        "name": name,
        "platforms": "PC",
        "source_url": source_url,
        "header_image": header_image,
        "source_site": source_site,
    }


if __name__ == "__main__":
    main()
