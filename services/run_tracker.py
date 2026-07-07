from __future__ import annotations

import sqlite3

from collectors.base import utc_now_iso


VALID_RUN_STATUSES = {"running", "ok", "warning", "error"}


class RunTracker:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def start_run(self, source: str) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO collection_runs (source, started_at, status)
            VALUES (?, ?, 'running')
            """,
            (source, utc_now_iso()),
        )
        self.connection.commit()
        return cursor.lastrowid

    def finish_run(
        self,
        run_id: int,
        status: str,
        jobs_found: int = 0,
        jobs_inserted: int = 0,
        error_message: str | None = None,
    ) -> None:
        if status not in VALID_RUN_STATUSES:
            raise ValueError(f"Unsupported run status: {status}")

        self.connection.execute(
            """
            UPDATE collection_runs
            SET finished_at = ?, status = ?, jobs_found = ?,
                jobs_inserted = ?, error_message = ?
            WHERE id = ?
            """,
            (utc_now_iso(), status, jobs_found, jobs_inserted, error_message, run_id),
        )
        self.connection.commit()

    def latest_run_per_source(self) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT r.*
            FROM collection_runs r
            JOIN (
                SELECT source, MAX(started_at) AS max_started
                FROM collection_runs
                GROUP BY source
            ) latest
                ON r.source = latest.source AND r.started_at = latest.max_started
            GROUP BY r.source
            HAVING r.id = MAX(r.id)
            ORDER BY r.source
            """
        )
        return list(cursor.fetchall())

    def runs_since(self, iso_timestamp: str) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT *
            FROM collection_runs
            WHERE started_at >= ?
            ORDER BY started_at, source
            """,
            (iso_timestamp,),
        )
        return list(cursor.fetchall())

    def had_jobs_recently(self, source: str, n_runs: int = 7) -> bool:
        cursor = self.connection.execute(
            """
            SELECT jobs_found
            FROM collection_runs
            WHERE source = ? AND status != 'running'
            ORDER BY started_at DESC, id DESC
            LIMIT ?
            """,
            (source, n_runs),
        )
        return any(row["jobs_found"] > 0 for row in cursor.fetchall())
