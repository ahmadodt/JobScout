from __future__ import annotations

import sqlite3


class CompanyWatchlist:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def add_company(self, name: str, careers_url: str | None = None) -> None:
        clean_name = name.strip()
        clean_url = (careers_url or "").strip() or None
        if not clean_name:
            raise ValueError("Company name is required")

        self.connection.execute(
            """
            INSERT INTO company_watchlist (name, careers_url, active)
            VALUES (?, ?, 1)
            ON CONFLICT(name) DO UPDATE SET
                careers_url = excluded.careers_url,
                active = 1
            """,
            (clean_name, clean_url),
        )
        self.connection.commit()

    def remove_company(self, name: str) -> None:
        self.connection.execute(
            """
            UPDATE company_watchlist
            SET active = 0
            WHERE name = ?
            """,
            (name,),
        )
        self.connection.commit()

    def list_companies(self) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT id, name, careers_url, added_at, active
            FROM company_watchlist
            WHERE active = 1
            ORDER BY lower(name)
            """
        )
        return list(cursor.fetchall())

    def get_company_stats(self, name: str) -> dict[str, int | str | None]:
        row = self.connection.execute(
            """
            SELECT
                COUNT(*) AS total_jobs,
                MAX(date_posted) AS latest_job_date,
                MAX(score) AS top_score
            FROM jobs
            WHERE lower(company) = lower(?)
            """,
            (name,),
        ).fetchone()

        return {
            "total_jobs": row["total_jobs"],
            "latest_job_date": row["latest_job_date"],
            "top_score": row["top_score"],
        }
