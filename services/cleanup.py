from __future__ import annotations

import sqlite3


def find_duplicates(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    cursor = connection.execute(
        """
        WITH duplicate_groups AS (
            SELECT lower(trim(title)) AS normalized_title,
                   lower(trim(company)) AS normalized_company
            FROM jobs
            GROUP BY normalized_title, normalized_company
            HAVING COUNT(*) > 1 AND COUNT(DISTINCT dedupe_key) > 1
        ), ranked_duplicates AS (
            SELECT jobs.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY lower(trim(title)), lower(trim(company))
                       ORDER BY id ASC
                   ) AS duplicate_rank
            FROM jobs
            JOIN duplicate_groups
              ON lower(trim(jobs.title)) = duplicate_groups.normalized_title
             AND lower(trim(jobs.company)) = duplicate_groups.normalized_company
        )
        SELECT *
        FROM ranked_duplicates
        WHERE duplicate_rank > 1
        ORDER BY lower(company), lower(title), id
        """
    )
    return list(cursor.fetchall())


def find_stale_jobs(connection: sqlite3.Connection, days: int = 30) -> list[sqlite3.Row]:
    cursor = connection.execute(
        """
        SELECT *
        FROM jobs
        WHERE status = 'new'
          AND datetime(date_collected) < datetime('now', ?)
        ORDER BY datetime(date_collected) ASC, id ASC
        """,
        (f"-{days} days",),
    )
    return list(cursor.fetchall())


def delete_jobs(connection: sqlite3.Connection, job_ids: list[int]) -> int:
    if not job_ids:
        return 0

    cursor = connection.executemany(
        "DELETE FROM jobs WHERE id = ?",
        [(job_id,) for job_id in job_ids],
    )
    connection.commit()
    return cursor.rowcount


def archive_stale_jobs(connection: sqlite3.Connection, days: int = 30) -> int:
    stale_jobs = find_stale_jobs(connection, days=days)
    if not stale_jobs:
        return 0

    cursor = connection.executemany(
        """
        UPDATE jobs
        SET status = 'ignored', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        [(job["id"],) for job in stale_jobs],
    )
    connection.commit()
    return cursor.rowcount
