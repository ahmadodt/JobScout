from __future__ import annotations

from pathlib import Path

import yaml

from database.db import connect, init_db
from services.job_store import JobStore
from services.scorer import score_job


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.yaml"


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def main() -> None:
    config = load_config()
    db_path = config.get("database", {}).get("path", "jobscout.sqlite3")

    connection = connect(ROOT_DIR / db_path)
    init_db(connection)
    store = JobStore(connection)

    jobs = list(
        connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE score IS NULL
            ORDER BY datetime(date_collected) DESC, id DESC
            """
        ).fetchall()
    )
    total = len(jobs)

    for index, job in enumerate(jobs, start=1):
        print(f"Scoring job {index} of {total}: {job['title']}")
        score, reason = score_job(
            title=job["title"],
            company=job["company"],
            location=job["location"],
            description=job["description"],
        )
        store.update_score(job["id"], score, reason)

    print(f"Scored {total} jobs")


if __name__ == "__main__":
    main()
