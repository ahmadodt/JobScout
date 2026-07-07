from __future__ import annotations

import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule

from services.config import DEFAULTS, load_config
from services.notifier import send_daily_summary, send_failure_alert


ROOT_DIR = Path(__file__).resolve().parent
LOG_DIR = ROOT_DIR / "logs"
LOG_PATH = LOG_DIR / "scheduler.log"
LAST_NEW_JOBS_COUNT = 0


def log(message: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"{line}\n")


def run_script(script_name: str, label: str) -> subprocess.CompletedProcess[str]:
    log(f"{label} started")
    result = subprocess.run(
        [sys.executable, script_name],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log(f"{label} stdout: {line}")
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            log(f"{label} stderr: {line}")

    if result.returncode == 0:
        log(f"{label} finished")
    else:
        log(f"{label} failed with exit code {result.returncode}")

    return result


def run_collection() -> None:
    global LAST_NEW_JOBS_COUNT

    result = run_script("run_collection.py", "Collection")
    if result.returncode == 0:
        LAST_NEW_JOBS_COUNT = _parse_count(result.stdout, r"Total new:\s*(\d+)")

    # Alert immediately on per-collector failures instead of waiting for
    # the daily summary email.
    send_failure_alert(logger=log)


def run_scoring() -> None:
    result = run_script("run_scoring.py", "Scoring")
    scored_jobs_count = 0
    if result.returncode == 0:
        scored_jobs_count = _parse_count(result.stdout, r"Scored\s+(\d+)\s+jobs")

    send_daily_summary(
        new_jobs_count=LAST_NEW_JOBS_COUNT,
        scored_jobs_count=scored_jobs_count,
        logger=log,
    )


def _parse_count(output: str, pattern: str) -> int:
    match = re.search(pattern, output)
    if not match:
        return 0
    return int(match.group(1))


def _validated_time(value: str, default: str) -> str:
    if isinstance(value, str) and re.fullmatch(r"\d{2}:\d{2}", value):
        hours, minutes = value.split(":")
        if int(hours) < 24 and int(minutes) < 60:
            return value
    log(f"Invalid schedule time {value!r} in config.yaml, falling back to {default}")
    return default


def main() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    config = load_config()
    schedule_config = config["schedule"]
    defaults = DEFAULTS["schedule"]

    collection_time = _validated_time(
        schedule_config["collection_time"], defaults["collection_time"]
    )
    scoring_time = _validated_time(
        schedule_config["scoring_time"], defaults["scoring_time"]
    )

    schedule.every().day.at(collection_time).do(run_collection)
    schedule.every().day.at(scoring_time).do(run_scoring)

    log("Scheduler started")
    log(f"Collection scheduled daily at {collection_time}")
    log(f"Scoring scheduled daily at {scoring_time}")
    if not config["scoring"]["ai_enabled"]:
        log("AI scoring disabled in config.yaml - scoring run will be a no-op")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log("Scheduler stopped")


if __name__ == "__main__":
    main()
