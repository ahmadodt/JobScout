from __future__ import annotations

from database.db import connect, init_db
from services.cleanup import archive_stale_jobs, delete_jobs, find_duplicates, find_stale_jobs
from services.config import load_config, resolve_db_path


def main() -> None:
    config = load_config()
    stale_days = config["cleanup"]["stale_days"]

    connection = connect(resolve_db_path(config))
    init_db(connection)

    duplicate_jobs = find_duplicates(connection)
    stale_jobs = find_stale_jobs(connection, days=stale_days)

    print(f"{len(duplicate_jobs)} duplicate jobs found")
    print(f"{len(stale_jobs)} stale jobs found (older than {stale_days} days, still new)")

    if not duplicate_jobs and not stale_jobs:
        print("No cleanup needed")
        return

    confirmation = input("Archive stale jobs and delete duplicate jobs? Type 'yes' to continue: ")
    if confirmation.strip().lower() != "yes":
        print("Cleanup cancelled")
        return

    deleted_count = delete_jobs(connection, [job["id"] for job in duplicate_jobs])
    archived_count = archive_stale_jobs(connection, days=stale_days)

    print(f"Deleted {deleted_count} duplicate jobs")
    print(f"Archived {archived_count} stale jobs")


if __name__ == "__main__":
    main()
