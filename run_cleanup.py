from __future__ import annotations

from pathlib import Path

import yaml

from database.db import connect, init_db
from services.cleanup import archive_stale_jobs, delete_jobs, find_duplicates, find_stale_jobs


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
STALE_DAYS = 30


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def main() -> None:
    config = load_config()
    db_path = config.get("database", {}).get("path", "jobscout.sqlite3")

    connection = connect(ROOT_DIR / db_path)
    init_db(connection)

    duplicate_jobs = find_duplicates(connection)
    stale_jobs = find_stale_jobs(connection, days=STALE_DAYS)

    print(f"{len(duplicate_jobs)} duplicate jobs found")
    print(f"{len(stale_jobs)} stale jobs found (older than {STALE_DAYS} days, still new)")

    if not duplicate_jobs and not stale_jobs:
        print("No cleanup needed")
        return

    confirmation = input("Archive stale jobs and delete duplicate jobs? Type 'yes' to continue: ")
    if confirmation.strip().lower() != "yes":
        print("Cleanup cancelled")
        return

    deleted_count = delete_jobs(connection, [job["id"] for job in duplicate_jobs])
    archived_count = archive_stale_jobs(connection, days=STALE_DAYS)

    print(f"Deleted {deleted_count} duplicate jobs")
    print(f"Archived {archived_count} stale jobs")


if __name__ == "__main__":
    main()
