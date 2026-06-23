from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import quote_plus

import requests

from app.cleaning import filter_videos
from app.config import DEFAULT_TARGET_RECORDS, MAX_WORKERS, SOURCE_TIMEOUT_SECONDS


BILIBILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"


@dataclass
class BilibiliVideo:
    title: str
    author: str
    stats: str
    video_url: str
    cover_url: str
    source_note: str


def bilibili_search_url(keyword: str) -> str:
    return f"https://search.bilibili.com/all?keyword={quote_plus(keyword)}"


def fetch_strategy_videos(game_name: str, limit: int = 6) -> list[BilibiliVideo]:
    return fetch_strategy_videos_bulk([game_name], limit=limit)


def fetch_strategy_videos_bulk(keywords: list[str], limit: int = DEFAULT_TARGET_RECORDS, workers: int = 4) -> list[BilibiliVideo]:
    search_terms = _build_search_terms(keywords)
    raw_records: list[dict] = []

    with ThreadPoolExecutor(max_workers=max(1, min(workers, MAX_WORKERS))) as executor:
        futures = {
            executor.submit(_fetch_bilibili_api_page, keyword, page): (keyword, page)
            for keyword in search_terms
            for page in range(1, 4)
        }
        for future in as_completed(futures):
            try:
                raw_records.extend(future.result())
            except requests.RequestException:
                continue
            raw_records = filter_videos(raw_records, limit=limit)
            if len(raw_records) >= limit:
                break

    if len(raw_records) < min(limit, 20):
        for keyword in search_terms[:3]:
            raw_records.extend(_fetch_bilibili_dynamic_page(keyword, page_limit=2))
            raw_records = filter_videos(raw_records, limit=limit)
            if len(raw_records) >= limit:
                break

    raw_records = filter_videos(raw_records, limit=limit)
    return [BilibiliVideo(**record) for record in raw_records]


def _fetch_bilibili_api_page(keyword: str, page: int) -> list[dict]:
    response = requests.get(
        BILIBILI_SEARCH_API,
        params={
            "search_type": "video",
            "keyword": f"{keyword} 攻略",
            "page": page,
            "page_size": 50,
        },
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://search.bilibili.com/",
        },
        timeout=SOURCE_TIMEOUT_SECONDS,
    )
    if response.status_code in {412, 429, 502, 503, 504}:
        return []
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        return []
    results = payload.get("data", {}).get("result", []) or []
    records: list[dict] = []
    for item in results:
        video_url = item.get("arcurl") or item.get("url") or ""
        records.append(
            {
                "title": _strip_html(item.get("title", "")),
                "author": item.get("author", "") or item.get("upic", ""),
                "stats": f"播放 {item.get('play', 0)} / 弹幕 {item.get('danmaku', 0)}",
                "video_url": video_url,
                "cover_url": item.get("pic", ""),
                "source_note": "api-fast",
            }
        )
    return records


def _fetch_bilibili_dynamic_page(keyword: str, page_limit: int = 2) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [_fallback_search_record(keyword, "未安装 Playwright，已提供动态搜索入口")]

    records: list[dict] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
            )
            page.goto(bilibili_search_url(f"{keyword} 攻略"), wait_until="domcontentloaded", timeout=SOURCE_TIMEOUT_SECONDS * 1000)
            for _ in range(page_limit):
                page.wait_for_timeout(900)
                page.mouse.wheel(0, 1200)
            cards = page.locator(".bili-video-card, .video-list .video-item, .video-item").all()
            for card in cards:
                title = _first_text(card, [".bili-video-card__info--tit", ".title", "a"])
                href = _first_attr(card, ["a"], "href")
                author = _first_text(card, [".bili-video-card__info--author", ".up-name", ".so-icon.up"])
                stats = _first_text(card, [".bili-video-card__stats", ".tags", ".so-icon.watch-num"])
                cover = _first_attr(card, ["img"], "src")
                if title and href:
                    records.append(
                        {
                            "title": title,
                            "author": author or "未知 UP 主",
                            "stats": stats or "暂无播放数据",
                            "video_url": _normalize_bilibili_url(href),
                            "cover_url": _normalize_bilibili_url(cover),
                            "source_note": "dynamic",
                        }
                    )
            browser.close()
    except Exception as exc:
        return [_fallback_search_record(keyword, f"动态抓取未完成：{exc.__class__.__name__}")]
    return records or [_fallback_search_record(keyword, "页面结构变化，已提供搜索入口")]


def _build_search_terms(keywords: list[str]) -> list[str]:
    seeds = [keyword.strip() for keyword in keywords if keyword and keyword.strip()]
    fallback = [
        "Dota 2",
        "CS2",
        "绝地求生",
        "Apex 英雄",
        "永劫无间",
        "黑神话悟空",
        "艾尔登法环",
        "赛博朋克2077",
        "原神",
        "幻兽帕鲁",
    ]
    terms = []
    for keyword in seeds + fallback:
        if keyword not in terms:
            terms.append(keyword)
    return terms


def _fallback_search_record(keyword: str, reason: str) -> dict:
    search_keyword = f"{keyword} 攻略"
    return {
        "title": f"在 Bilibili 搜索「{search_keyword}」",
        "author": "Bilibili 搜索",
        "stats": reason,
        "video_url": bilibili_search_url(search_keyword),
        "cover_url": "",
        "source_note": "dynamic-fallback",
    }


def _strip_html(value: str) -> str:
    return value.replace('<em class="keyword">', "").replace("</em>", "").replace("<em>", "").strip()


def _first_text(locator, selectors: list[str]) -> str:
    for selector in selectors:
        try:
            target = locator.locator(selector).first
            if target.count():
                text = target.inner_text(timeout=800).strip()
                if text:
                    return " ".join(text.split())
        except Exception:
            continue
    return ""


def _first_attr(locator, selectors: list[str], attr: str) -> str:
    for selector in selectors:
        try:
            target = locator.locator(selector).first
            if target.count():
                value = target.get_attribute(attr, timeout=800)
                if value:
                    return value.strip()
        except Exception:
            continue
    return ""


def _normalize_bilibili_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"https://www.bilibili.com{url}"
    return url
