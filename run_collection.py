from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from collectors.base import Collector
from collectors.registry import build_collectors
from database.db import connect, init_db
from services.config import load_config, resolve_db_path
from services.job_store import JobStore
from services.run_tracker import RunTracker


ROOT_DIR = Path(__file__).resolve().parent
LOG_DIR = ROOT_DIR / "logs"

logger = logging.getLogger("run_collection")


def _setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "collection.log", encoding="utf-8"),
        ],
    )


def _is_within_lookback(date_posted: str | None, cutoff: date) -> bool:
    if not date_posted:
        return True
    try:
        posted = date.fromisoformat(date_posted[:10])
    except ValueError:
        return True
    return posted >= cutoff


def _has_parseable_date(date_posted: str | None) -> bool:
    if not date_posted:
        return False
    try:
        date.fromisoformat(date_posted[:10])
    except ValueError:
        return False
    return True


def collect_all(
    collectors: list[tuple[str, Collector]],
    store: JobStore,
    tracker: RunTracker,
    cutoff: date,
    lookback_days: int,
) -> tuple[int, int, int]:
    total_collected = 0
    total_new = 0
    total_skipped = 0

    for name, collector in collectors:
        run_id = tracker.start_run(name)
        logger.info("%s: starting collection", name)
        try:
            jobs = collector.collect()
        except Exception as exc:
            logger.exception("%s: collector failed", name)
            tracker.finish_run(
                run_id, "error", error_message=f"{type(exc).__name__}: {exc}"
            )
            continue

        recent_jobs = [job for job in jobs if _is_within_lookback(job.date_posted, cutoff)]
        skipped = len(jobs) - len(recent_jobs)
        undated = sum(1 for job in jobs if not _has_parseable_date(job.date_posted))
        new_count = store.insert_jobs(recent_jobs)

        total_collected += len(jobs)
        total_new += new_count
        total_skipped += skipped

        status = "ok"
        if not jobs and tracker.had_jobs_recently(name):
            status = "warning"
            logger.warning(
                "%s: returned 0 jobs but had jobs in recent runs - possible breakage",
                name,
            )
        tracker.finish_run(
            run_id, status, jobs_found=len(jobs), jobs_inserted=new_count
        )

        message = f"{name}: collected {len(jobs)} jobs, inserted {new_count} new jobs"
        if skipped:
            message += f", skipped {skipped} older than {lookback_days} days"
        if undated:
            message += f", {undated} without a parseable date_posted"
        logger.info(message)

    return total_collected, total_new, total_skipped


def main() -> None:
    _setup_logging()
    config = load_config()
    lookback_days = config["collection"]["lookback_days"]
    cutoff = date.today() - timedelta(days=lookback_days)

    connection = connect(resolve_db_path(config))
    init_db(connection)
    store = JobStore(connection)
    tracker = RunTracker(connection)

    collectors = build_collectors(config)
    total_collected, total_new, total_skipped = collect_all(
        collectors, store, tracker, cutoff, lookback_days
    )

    print(f"Total collected: {total_collected}")
    print(f"Total skipped (older than {lookback_days} days): {total_skipped}")
    print(f"Total new: {total_new}")


if __name__ == "__main__":
    main()
