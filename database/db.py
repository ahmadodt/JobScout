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
    # Streamlit holds a long-lived connection while collection/scoring write;
    # WAL lets readers and one writer coexist without "database is locked".
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    connection.executescript(schema)
    _ensure_score_columns(connection)
    _ensure_company_watchlist_table(connection)
    _ensure_dedupe_key_includes_location(connection)
    connection.commit()


def _ensure_score_columns(connection: sqlite3.Connection) -> None:
    cursor = connection.execute("PRAGMA table_info(jobs)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "score" not in existing_columns:
        connection.execute("ALTER TABLE jobs ADD COLUMN score INTEGER")
    if "score_reason" not in existing_columns:
        connection.execute("ALTER TABLE jobs ADD COLUMN score_reason TEXT")
    if "score_source" not in existing_columns:
        connection.execute("ALTER TABLE jobs ADD COLUMN score_source TEXT")
        connection.execute(
            "UPDATE jobs SET score_source = 'ai' "
            "WHERE score IS NOT NULL AND score_source IS NULL"
        )


def _ensure_dedupe_key_includes_location(connection: sqlite3.Connection) -> None:
    """One-time migration: dedupe_key grew from company::title to
    company::title::location so one posting per location is kept.

    Old keys contain exactly one '::'; rows are rekeyed in place. If two
    rows collide under the new key they were true duplicates - the oldest
    row (lowest id) wins.
    """
    old_rows = connection.execute(
        """
        SELECT id, company, title, location
        FROM jobs
        WHERE (length(dedupe_key) - length(replace(dedupe_key, '::', ''))) / 2 = 1
        ORDER BY id
        """
    ).fetchall()
    if not old_rows:
        return

    from services.deduplicator import make_dedupe_key

    seen_keys = {
        row["dedupe_key"]
        for row in connection.execute(
            "SELECT dedupe_key FROM jobs "
            "WHERE (length(dedupe_key) - length(replace(dedupe_key, '::', ''))) / 2 != 1"
        )
    }
    for row in old_rows:
        new_key = make_dedupe_key(row["company"], row["title"], row["location"])
        if new_key in seen_keys:
            connection.execute("DELETE FROM jobs WHERE id = ?", (row["id"],))
            continue
        connection.execute(
            "UPDATE jobs SET dedupe_key = ? WHERE id = ?", (new_key, row["id"])
        )
        seen_keys.add(new_key)


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
