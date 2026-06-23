from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher

from .cleaning import filter_steam_details, filter_steam_popular
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


def replace_steam_popular(records: Iterable[dict]) -> None:
    rows = filter_steam_popular(records)
    with connect() as conn:
        conn.execute("DELETE FROM steam_popular_current")
        conn.executemany(
            """
            INSERT INTO steam_popular_current (
                app_id, rank_index, name, release_date, discount_text, final_price,
                review_summary, platforms, source_url, scraped_at
            )
            VALUES (
                :app_id, :rank_index, :name, :release_date, :discount_text, :final_price,
                :review_summary, :platforms, :source_url, :scraped_at
            )
            """,
            rows,
        )


def replace_steam_details(records: Iterable[dict]) -> None:
    rows = filter_steam_details(records)
    with connect() as conn:
        conn.execute("DELETE FROM steam_app_details_current")
        conn.executemany(
            """
            INSERT INTO steam_app_details_current (
                app_id, name, is_free, developers, publishers, genres, categories,
                supported_languages, short_description, header_image, detail_url, scraped_at
            )
            VALUES (
                :app_id, :name, :is_free, :developers, :publishers, :genres, :categories,
                :supported_languages, :short_description, :header_image, :detail_url, :scraped_at
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
        steam_rows = conn.execute(
            """
            SELECT p.*, d.genres, d.categories, d.short_description, d.header_image, d.detail_url
            FROM steam_popular_current p
            LEFT JOIN steam_app_details_current d ON d.app_id = p.app_id
            ORDER BY p.rank_index ASC
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
            "steam_popular_count": conn.execute("SELECT COUNT(*) FROM steam_popular_current").fetchone()[0],
            "steam_detail_count": conn.execute("SELECT COUNT(*) FROM steam_app_details_current").fetchone()[0],
            "bilibili_area_count": conn.execute("SELECT COUNT(*) FROM bilibili_live_current").fetchone()[0],
            "last_bilibili_peak": conn.execute("SELECT COALESCE(MAX(online), 0) FROM bilibili_live_current").fetchone()[0],
        }

    steam_games = [_shape_game(row) for row in steam_rows]
    all_bilibili_areas = [dict(row) for row in bilibili_rows]
    return {
        "metrics": metrics,
        "steam_games": steam_games,
        "bilibili_areas": all_bilibili_areas[:20],
        "matches": build_matches(steam_games, all_bilibili_areas),
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
            SELECT p.*, d.is_free, d.developers, d.publishers, d.genres, d.categories,
                   d.short_description, d.header_image, d.detail_url
            FROM steam_popular_current p
            LEFT JOIN steam_app_details_current d ON d.app_id = p.app_id
            ORDER BY p.rank_index ASC
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


def build_matches(steam_games: list[dict], bilibili_areas: list[dict]) -> list[dict]:
    by_area = {normalize_name(item["area_name"]): item for item in bilibili_areas}
    matches: list[dict] = []
    for game in steam_games:
        area = by_area.get(normalize_name(game["name"]))
        if not area:
            continue
        steam_score = max(1, 21 - int(game["rank_index"]))
        bilibili_score = min(100, int(area["online"]) // 5000)
        matches.append(
            {
                "game_name": game["name"],
                "steam_rank": game["rank_index"],
                "area_name": area["area_name"],
                "online": area["online"],
                "price": game["final_price"] or ("免费" if game.get("is_free") else "暂无"),
                "genres": game.get("genres", ""),
                "combined_score": steam_score * 0.6 + bilibili_score * 0.4,
            }
        )
    matches.sort(key=lambda item: item["combined_score"], reverse=True)
    return matches[:10]


def build_player_diagnosis(game: dict, live_area: dict | None) -> dict:
    rank = int(game.get("rank_index") or 99)
    online = int(live_area.get("online") or 0) if live_area else 0
    if rank <= 5 and online >= 100000:
        return {
            "label": "热门爆款",
            "summary": "Steam 热门榜和 B站直播热度同时靠前，适合先看攻略再入坑。",
            "advice": "优先查看新手教程、版本强势玩法和配置优化视频。",
        }
    if rank <= 10 and online < 30000:
        return {
            "label": "Steam 热门但 B站讨论较少",
            "summary": "购买热度较高，但国内直播侧声量不算强，可能更适合自己探索。",
            "advice": "建议优先看评测和上手指南，再判断玩法是否合口味。",
        }
    if rank > 10 and online >= 100000:
        return {
            "label": "直播话题型游戏",
            "summary": "B站观看热度高于 Steam 榜单位置，可能是直播效果好或近期有事件带动。",
            "advice": "建议先看实况和避坑视频，确认自己玩是否也有同样乐趣。",
        }
    return {
        "label": "常规关注",
        "summary": "当前热度适中，可以通过基础信息和攻略视频快速判断是否值得投入时间。",
        "advice": "先看官方介绍、系统需求和近期攻略更新时间。",
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
    return {
        **game,
        "app_id": app_id,
        "detail_url": game.get("detail_url") or game.get("source_url") or f"https://store.steampowered.com/app/{app_id}/",
        "source_url": game.get("source_url") or game.get("detail_url") or f"https://store.steampowered.com/app/{app_id}/",
        "header_image": game.get("header_image") or "",
        "short_description": game.get("short_description") or "暂无简介，可点击 Steam 商店页查看完整介绍。",
        "genres": game.get("genres") or "暂无类型标签",
        "final_price": game.get("final_price") or ("免费" if game.get("is_free") else "暂无"),
    }
