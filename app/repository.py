from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher

from .cleaning import filter_game_catalog
from .db import connect
from .utils import normalize_name, utc_now_iso


def begin_run(source: str) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO crawl_runs (source, status, started_at)
            VALUES (?, 'running', ?)
            """,
            (source, utc_now_iso()),
        )
        return int(cursor.lastrowid)


def finish_run(run_id: int, status: str, record_count: int = 0, error_message: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE crawl_runs
            SET status = ?, finished_at = ?, record_count = ?, error_message = ?
            WHERE id = ?
            """,
            (status, utc_now_iso(), record_count, error_message, run_id),
        )


def replace_game_catalog(records: Iterable[dict]) -> None:
    rows = filter_game_catalog(records)
    with connect() as conn:
        conn.execute("DELETE FROM game_catalog_current")
        conn.executemany(
            """
            INSERT INTO game_catalog_current (
                app_id, rank_index, name, platforms, source_url, header_image, source_site, scraped_at
            )
            VALUES (
                :app_id, :rank_index, :name, :platforms, :source_url, :header_image, :source_site, :scraped_at
            )
            """,
            rows,
        )


def replace_bilibili_live(records: Iterable[dict]) -> None:
    rows = list(records)
    with connect() as conn:
        conn.execute("DELETE FROM bilibili_live_current")
        conn.executemany(
            """
            INSERT INTO bilibili_live_current (
                area_id, parent_area_id, parent_area_name, area_name, room_id,
                room_title, streamer_name, online, tags, cover_url, room_url, scraped_at
            )
            VALUES (
                :area_id, :parent_area_id, :parent_area_name, :area_name, :room_id,
                :room_title, :streamer_name, :online, :tags, :cover_url, :room_url, :scraped_at
            )
            """,
            rows,
        )
        conn.executemany(
            """
            INSERT INTO bilibili_live_history (
                area_id, room_id, online, room_title, captured_at
            )
            VALUES (
                :area_id, :room_id, :online, :room_title, :scraped_at
            )
            """,
            rows,
        )


def fetch_dashboard_data() -> dict:
    with connect() as conn:
        game_rows = conn.execute(
            """
            SELECT *
            FROM game_catalog_current
            ORDER BY rank_index ASC
            LIMIT 20
            """
        ).fetchall()
        bilibili_rows = conn.execute(
            """
            SELECT *
            FROM bilibili_live_current
            ORDER BY online DESC
            """
        ).fetchall()
        run_rows = conn.execute(
            """
            SELECT source, status, started_at, finished_at, record_count, error_message
            FROM crawl_runs
            WHERE id IN (
                SELECT MAX(id)
                FROM crawl_runs
                GROUP BY source
            )
            ORDER BY source
            """
        ).fetchall()
        metrics = {
            "game_count": conn.execute("SELECT COUNT(*) FROM game_catalog_current").fetchone()[0],
            "bilibili_area_count": conn.execute("SELECT COUNT(*) FROM bilibili_live_current").fetchone()[0],
            "last_bilibili_peak": conn.execute("SELECT COALESCE(MAX(online), 0) FROM bilibili_live_current").fetchone()[0],
        }

    return {
        "metrics": metrics,
        "games": [_shape_game(row) for row in game_rows],
        "bilibili_areas": [dict(row) for row in bilibili_rows[:20]],
        "source_runs": [dict(row) for row in run_rows],
        "generated_at": utc_now_iso(),
    }


def search_game_by_name(query: str) -> dict | None:
    normalized_query = normalize_name(query)
    if not normalized_query:
        return None

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM game_catalog_current
            ORDER BY rank_index ASC
            """
        ).fetchall()
        areas = conn.execute(
            """
            SELECT *
            FROM bilibili_live_current
            ORDER BY online DESC
            """
        ).fetchall()

    if not rows:
        return None

    scored_rows = []
    for row in rows:
        game = dict(row)
        normalized_name = normalize_name(game["name"])
        score = SequenceMatcher(None, normalized_query, normalized_name).ratio()
        if normalized_query in normalized_name or normalized_name in normalized_query:
            score += 0.35
        scored_rows.append((score, game))

    score, best = max(scored_rows, key=lambda item: item[0])
    if score < 0.28:
        return None

    game = _shape_game(best)
    matched_area = _match_area(game["name"], [dict(row) for row in areas])
    return {
        "game": game,
        "live_area": matched_area,
        "diagnosis": build_player_diagnosis(game, matched_area),
        "match_score": round(min(score, 1.0), 3),
    }


def build_player_diagnosis(game: dict, live_area: dict | None) -> dict:
    rank = int(game.get("rank_index") or 99)
    online = int(live_area.get("online") or 0) if live_area else 0
    if rank <= 5 and online >= 100000:
        return {
            "label": "热门爆款",
            "summary": "静态游戏目录排名靠前，B站直播热度也高，适合优先展示和推荐。",
            "advice": "建议优先提供新手教程、实况攻略和配置优化视频。",
        }
    if rank <= 10 and online < 30000:
        return {
            "label": "高关注但直播讨论较少",
            "summary": "游戏本身在目录中靠前，但当前 B站直播声量不强。",
            "advice": "建议补充评测和上手指南，帮助用户判断是否适合自己。",
        }
    if rank > 10 and online >= 100000:
        return {
            "label": "直播话题型游戏",
            "summary": "B站观看热度高于游戏目录位置，可能是赛事、主播或热点事件带动。",
            "advice": "建议优先查看实况和避坑视频，再判断是否值得游玩。",
        }
    return {
        "label": "常规关注",
        "summary": "当前热度适中，可以通过基础信息和攻略视频快速了解游戏。",
        "advice": "建议先看来源页面、近期攻略和直播间内容。",
    }


def _match_area(game_name: str, bilibili_areas: list[dict]) -> dict | None:
    normalized = normalize_name(game_name)
    for area in bilibili_areas:
        if normalize_name(area["area_name"]) == normalized:
            return area
    return None


def _shape_game(row) -> dict:
    game = dict(row)
    app_id = int(game["app_id"])
    source_site = game.get("source_site") or "静态游戏目录"
    return {
        **game,
        "app_id": app_id,
        "detail_url": game.get("source_url") or f"https://store.steampowered.com/app/{app_id}/",
        "source_url": game.get("source_url") or f"https://store.steampowered.com/app/{app_id}/",
        "header_image": game.get("header_image") or "",
        "short_description": f"来自{source_site}的游戏条目，可点击来源页面查看完整介绍。",
    }
