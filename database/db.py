from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "jobscout.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    connection.executescript(schema)
    _ensure_score_columns(connection)
    _ensure_company_watchlist_table(connection)
    connection.commit()


def _ensure_score_columns(connection: sqlite3.Connection) -> None:
    cursor = connection.execute("PRAGMA table_info(jobs)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "score" not in existing_columns:
        connection.execute("ALTER TABLE jobs ADD COLUMN score INTEGER")
    if "score_reason" not in existing_columns:
        connection.execute("ALTER TABLE jobs ADD COLUMN score_reason TEXT")


def _ensure_company_watchlist_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS company_watchlist (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            careers_url TEXT,
            added_at TEXT DEFAULT (datetime('now')),
            active INTEGER DEFAULT 1
        )
        """
    )
