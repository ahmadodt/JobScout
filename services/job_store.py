from __future__ import annotations

import sqlite3

from collectors.base import Job
from services.deduplicator import make_dedupe_key


VALID_STATUSES = {"new", "relevant", "ignored", "applied"}
VALID_SCORE_SOURCES = {"ai", "manual"}


class JobStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def insert_job(self, job: Job) -> bool:
        dedupe_key = make_dedupe_key(job.company, job.title)
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO jobs (
                title,
                company,
                location,
                source,
                url,
                description,
                date_posted,
                date_collected,
                dedupe_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.title,
                job.company,
                job.location,
                job.source,
                job.url,
                job.description,
                job.date_posted,
                job.date_collected,
                dedupe_key,
            ),
        )
        return cursor.rowcount == 1

    def insert_jobs(self, jobs: list[Job]) -> int:
        new_count = 0
        for job in jobs:
            if self.insert_job(job):
                new_count += 1
        self.connection.commit()
        return new_count

    def list_jobs(
        self,
        source: str | None = None,
        status: str | None = None,
        company: str | None = None,
        keyword: str | None = None,
        sort_by: str = "newest",
        min_score: int | None = None,
    ) -> list[sqlite3.Row]:
        where_clauses = []
        params: list[str | int] = []

        if source:
            where_clauses.append("source = ?")
            params.append(source)
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if company:
            where_clauses.append("company = ?")
            params.append(company)
        if keyword:
            where_clauses.append(
                "(title LIKE ? OR company LIKE ? OR location LIKE ? OR description LIKE ?)"
            )
            pattern = f"%{keyword}%"
            params.extend([pattern, pattern, pattern, pattern])
        if min_score is not None and min_score > 1:
            where_clauses.append("score >= ?")
            params.append(min_score)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        if sort_by == "score":
            order_sql = """
            CASE WHEN score IS NULL THEN 1 ELSE 0 END,
            score DESC,
            datetime(date_collected) DESC,
            id DESC
            """
        elif sort_by == "newest":
            order_sql = "datetime(date_collected) DESC, id DESC"
        else:
            raise ValueError(f"Unsupported sort option: {sort_by}")

        cursor = self.connection.execute(
            f"""
            SELECT *
            FROM jobs
            {where_sql}
            ORDER BY {order_sql}
            """,
            params,
        )
        return list(cursor.fetchall())

    def update_status(self, job_id: int, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Unsupported job status: {status}")

        self.connection.execute(
            """
            UPDATE jobs
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, job_id),
        )
        self.connection.commit()

    def update_score(
        self,
        job_id: int,
        score: int,
        reason: str,
        source: str = "ai",
    ) -> None:
        if source not in VALID_SCORE_SOURCES:
            raise ValueError(f"Unsupported score source: {source}")
        if not 1 <= score <= 10:
            raise ValueError(f"Score must be between 1 and 10, got {score}")

        self.connection.execute(
            """
            UPDATE jobs
            SET score = ?, score_reason = ?, score_source = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (score, reason, source, job_id),
        )
        self.connection.commit()

    def get_filter_values(self) -> dict[str, list[str]]:
        values = {}
        for column in ("source", "status", "company"):
            cursor = self.connection.execute(
                f"SELECT DISTINCT {column} FROM jobs ORDER BY {column}"
            )
            values[column] = [row[0] for row in cursor.fetchall()]
        return values
