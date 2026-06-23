from __future__ import annotations

from collections.abc import Iterable
from typing import Any


INVALID_TEXT_MARKERS = {
    "",
    "-",
    "--",
    "null",
    "none",
    "undefined",
    "暂无",
    "未知",
}

STATIC_GAME_BLOCKLIST = {
    "感谢你的投递",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def is_valid_text(value: Any, min_length: int = 1) -> bool:
    text = clean_text(value)
    return len(text) >= min_length and text.lower() not in INVALID_TEXT_MARKERS


def clean_url(value: Any) -> str:
    text = clean_text(value)
    if text.startswith("//"):
        return f"https:{text}"
    return text


def dedupe_records(
    records: Iterable[dict],
    key_fields: list[str],
    required_fields: list[str],
    limit: int | None = None,
) -> list[dict]:
    seen: set[tuple[str, ...]] = set()
    cleaned: list[dict] = []
    for record in records:
        normalized = {key: clean_text(value) if isinstance(value, str) else value for key, value in record.items()}
        for key, value in list(normalized.items()):
            if key.endswith("_url") or key in {"source_url", "detail_url", "video_url", "cover_url", "room_url"}:
                normalized[key] = clean_url(value)
        if any(not is_valid_text(normalized.get(field)) for field in required_fields):
            continue
        dedupe_key = tuple(clean_text(normalized.get(field)).lower() for field in key_fields)
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        cleaned.append(normalized)
        if limit and len(cleaned) >= limit:
            break
    return cleaned


def filter_game_catalog(records: Iterable[dict], limit: int | None = None) -> list[dict]:
    return dedupe_records(records, ["app_id"], ["app_id", "name", "source_url"], limit)


def filter_static_games(records: Iterable[dict], limit: int | None = None) -> list[dict]:
    candidates = dedupe_records(records, ["source_url"], ["name", "source_url"])
    cleaned = []
    for record in candidates:
        name = clean_text(record.get("name"))
        source_url = clean_url(record.get("source_url")).lower()
        if name in STATIC_GAME_BLOCKLIST or "thank-you-for-your-application" in source_url:
            continue
        cleaned.append(record)
        if limit and len(cleaned) >= limit:
            break
    return cleaned


def filter_videos(records: Iterable[dict], limit: int | None = None) -> list[dict]:
    return dedupe_records(records, ["video_url"], ["title", "video_url"], limit)


def filter_bilibili_live(records: Iterable[dict], limit: int | None = None) -> list[dict]:
    return dedupe_records(records, ["room_id"], ["room_id", "room_title", "room_url"], limit)
