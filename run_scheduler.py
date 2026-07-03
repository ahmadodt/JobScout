from __future__ import annotations

import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule

from services.notifier import send_daily_summary


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


def main() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    schedule.every().day.at("08:00").do(run_collection)
    schedule.every().day.at("08:30").do(run_scoring)

    log("Scheduler started")
    log("Collection scheduled daily at 08:00")
    log("Scoring scheduled daily at 08:30")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log("Scheduler stopped")


if __name__ == "__main__":
    main()
