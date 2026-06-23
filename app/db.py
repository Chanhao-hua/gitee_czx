import sqlite3
from contextlib import contextmanager

from .config import DATA_DIR, DB_PATH


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def connect():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS crawl_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                record_count INTEGER DEFAULT 0,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS steam_popular_current (
                app_id INTEGER PRIMARY KEY,
                rank_index INTEGER NOT NULL,
                name TEXT NOT NULL,
                release_date TEXT,
                discount_text TEXT,
                final_price TEXT,
                review_summary TEXT,
                platforms TEXT,
                source_url TEXT NOT NULL,
                scraped_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS steam_app_details_current (
                app_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                is_free INTEGER NOT NULL,
                developers TEXT,
                publishers TEXT,
                genres TEXT,
                categories TEXT,
                supported_languages TEXT,
                short_description TEXT,
                header_image TEXT,
                detail_url TEXT,
                scraped_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bilibili_live_current (
                area_id INTEGER PRIMARY KEY,
                parent_area_id INTEGER NOT NULL,
                parent_area_name TEXT NOT NULL,
                area_name TEXT NOT NULL,
                room_id INTEGER NOT NULL,
                room_title TEXT NOT NULL,
                streamer_name TEXT NOT NULL,
                online INTEGER NOT NULL,
                tags TEXT,
                cover_url TEXT,
                room_url TEXT NOT NULL,
                scraped_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bilibili_live_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                online INTEGER NOT NULL,
                room_title TEXT NOT NULL,
                captured_at TEXT NOT NULL
            );
            """
        )
