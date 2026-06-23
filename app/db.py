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

            CREATE TABLE IF NOT EXISTS game_catalog_current (
                app_id INTEGER PRIMARY KEY,
                rank_index INTEGER NOT NULL,
                name TEXT NOT NULL,
                platforms TEXT,
                source_url TEXT NOT NULL,
                header_image TEXT,
                source_site TEXT,
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
        _migrate_legacy_game_catalog(conn)
        _ensure_column(conn, "game_catalog_current", "header_image", "TEXT")
        _ensure_column(conn, "game_catalog_current", "source_site", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    existing_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing_columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _migrate_legacy_game_catalog(conn: sqlite3.Connection) -> None:
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "steam_popular_current" not in tables:
        return
    current_count = conn.execute("SELECT COUNT(*) FROM game_catalog_current").fetchone()[0]
    if current_count == 0:
        conn.execute(
            """
            INSERT INTO game_catalog_current (
                app_id, rank_index, name, platforms, source_url, scraped_at
            )
            SELECT app_id, rank_index, name, platforms, source_url, scraped_at
            FROM steam_popular_current
            """
        )
    conn.execute("DROP TABLE steam_popular_current")
