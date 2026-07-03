from __future__ import annotations

from pathlib import Path

import yaml

from collectors.bmw import BMWCollector
from collectors.mock import MockCollector
from collectors.porsche import PorscheCollector
from database.db import connect, init_db
from services.job_store import JobStore


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.yaml"

AVAILABLE_COLLECTORS = {
    "mock": MockCollector,
    "bmw": BMWCollector,
    "porsche": PorscheCollector,
}


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def main() -> None:
    config = load_config()
    db_path = config.get("database", {}).get("path", "jobscout.sqlite3")
    collectors_config = config.get("collectors", {})

    connection = connect(ROOT_DIR / db_path)
    init_db(connection)
    store = JobStore(connection)

    total_collected = 0
    total_new = 0

    for name, collector_class in AVAILABLE_COLLECTORS.items():
        collector_config = collectors_config.get(name, {})
        if not collector_config.get("enabled", False):
            continue

        collector = collector_class()
        jobs = collector.collect()
        new_count = store.insert_jobs(jobs)

        total_collected += len(jobs)
        total_new += new_count
        print(f"{name}: collected {len(jobs)} jobs, inserted {new_count} new jobs")

    print(f"Total collected: {total_collected}")
    print(f"Total new: {total_new}")


if __name__ == "__main__":
    main()
