from __future__ import annotations

from pathlib import Path

import yaml

from database.db import connect, init_db
from services.exporter import export_jobs_html


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
    count, output_path = export_jobs_html(connection)
    relative_path = output_path.relative_to(ROOT_DIR)
    print(f"Exported {count} jobs to {relative_path.as_posix()}")


if __name__ == "__main__":
    main()
