from __future__ import annotations

from database.db import connect, init_db
from services.config import load_config, resolve_db_path
from services.job_store import JobStore
from services.scorer import score_job


def main() -> None:
    config = load_config()

    if not config["scoring"]["ai_enabled"]:
        print("AI scoring disabled in config.yaml (scoring.ai_enabled: false)")
        print("Scored 0 jobs")
        return

    connection = connect(resolve_db_path(config))
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
    scored = 0
    failed = 0

    for index, job in enumerate(jobs, start=1):
        print(f"Scoring job {index} of {total}: {job['title']}")
        result = score_job(
            title=job["title"],
            company=job["company"],
            location=job["location"],
            description=job["description"],
        )
        if result is None:
            failed += 1
            print(f"Scoring failed for job {job['id']}, will retry next run")
            continue

        score, reason = result
        store.update_score(job["id"], score, reason, source="ai")
        scored += 1

    print(f"Scored {scored} jobs")
    if failed:
        print(f"Failed {failed} jobs (left unscored for retry)")


if __name__ == "__main__":
    main()
