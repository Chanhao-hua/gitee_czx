from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..cleaning import filter_static_games
from ..config import DEFAULT_TARGET_RECORDS, SOURCE_TIMEOUT_SECONDS


GAMERSKY_URL = "https://ku.gamersky.com/"
ALI213_URLS = [
    "https://www.ali213.net/zt/index_p1.html",
    "https://www.ali213.net/zt/index_p2.html",
    "https://www.ali213.net/zt/index_p3.html",
    "https://www.ali213.net/zt/index_p4.html",
    "https://www.ali213.net/zt/ztisitemap_hot.html",
    "https://www.ali213.net/zt/ztisitemap_sale.html",
    "https://www.ali213.net/zt/zhuanti.html",
]


@dataclass
class StaticGameInfo:
    app_id: int
    rank_index: int
    name: str
    release_date: str
    discount_text: str
    final_price: str
    review_summary: str
    platforms: str
    source_url: str
    header_image: str
    source_site: str


def fetch_static_games(limit: int = DEFAULT_TARGET_RECORDS) -> list[StaticGameInfo]:
    records = _fetch_gamersky()
    if len(records) < limit:
        for url in ALI213_URLS:
            records.extend(_fetch_ali213(url))
            records = filter_static_games(records, limit=limit)
            if len(records) >= limit:
                break
    records = filter_static_games(records, limit=limit)
    for index, record in enumerate(records, start=1):
        record["app_id"] = int(record.get("app_id") or index)
        record["rank_index"] = index
    return [StaticGameInfo(**record) for record in records[:limit]]


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


def _fetch_ali213(url: str) -> list[dict]:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=SOURCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    records = []
    blocked = {"syzt", "ztisitemap_sale", "ztisitemap_hot", "zhuanti"}
    for index, link in enumerate(soup.select("a[href*='/zt/']"), start=1):
        href = link.get("href", "")
        slug = href.rstrip("/").split("/")[-1].replace(".html", "")
        name = link.get_text(" ", strip=True) or slug.replace("-", " ")
        if (
            not name
            or "/zt/" not in href
            or slug in blocked
            or slug.startswith("index_p")
            or href.endswith(".png")
            or href.endswith(".js")
        ):
            continue
        records.append(
            _record(
                app_id=900000 + index,
                name=name,
                source_url=urljoin(url, href),
                header_image="",
                source_site="游侠专题库",
            )
        )
    return records


def _record(app_id: int, name: str, source_url: str, header_image: str, source_site: str) -> dict:
    return {
        "app_id": app_id,
        "rank_index": 0,
        "name": name,
        "release_date": "",
        "discount_text": "",
        "final_price": "",
        "review_summary": "",
        "platforms": "PC",
        "source_url": source_url,
        "header_image": header_image,
        "source_site": source_site,
    }
