from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule


ROOT_DIR = Path(__file__).resolve().parent
LOG_DIR = ROOT_DIR / "logs"
LOG_PATH = LOG_DIR / "scheduler.log"


def log(message: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"{line}\n")


def run_script(script_name: str, label: str) -> None:
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


def run_collection() -> None:
    run_script("run_collection.py", "Collection")


def run_scoring() -> None:
    run_script("run_scoring.py", "Scoring")


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
