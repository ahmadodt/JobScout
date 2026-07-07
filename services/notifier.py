from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

import yaml

from database.db import connect, init_db


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.yaml"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
REQUIRED_ENV_VARS = (
    "JOBSCOUT_EMAIL_FROM",
    "JOBSCOUT_EMAIL_TO",
    "JOBSCOUT_EMAIL_PASSWORD",
)


def send_daily_summary(
    new_jobs_count: int,
    scored_jobs_count: int,
    logger: Callable[[str], None] | None = None,
) -> bool:
    missing_vars = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing_vars:
        _log(
            logger,
            "Notification skipped: missing environment variables "
            + ", ".join(missing_vars),
        )
        return False

    sender = os.environ["JOBSCOUT_EMAIL_FROM"]
    recipient = os.environ["JOBSCOUT_EMAIL_TO"]
    password = os.environ["JOBSCOUT_EMAIL_PASSWORD"]
    top_jobs = _get_top_scoring_jobs()
    health = _get_collection_health()
    failures = sum(1 for entry in health if entry["status"] == "error")

    subject = "JobScout daily summary"
    if failures:
        plural = "s" if failures != 1 else ""
        subject += f" - {failures} collector failure{plural}"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        _build_summary_body(new_jobs_count, scored_jobs_count, top_jobs, health)
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(sender, password)
            smtp.send_message(message)
    except Exception as exc:
        _log(logger, f"Notification failed: {exc}")
        return False

    _log(logger, f"Notification sent to {recipient}")
    return True


def _build_summary_body(
    new_jobs_count: int,
    scored_jobs_count: int,
    top_jobs: list[dict[str, str | int | None]],
    health: list[dict[str, str | int | None]] | None = None,
) -> str:
    lines = [
        "JobScout daily summary",
        "",
        f"New jobs collected today: {new_jobs_count}",
        f"Jobs scored: {scored_jobs_count}",
        "",
        "Top 5 highest scoring jobs:",
    ]

    if not top_jobs:
        lines.append("No scored jobs found.")
    else:
        for index, job in enumerate(top_jobs, start=1):
            lines.extend(
                [
                    f"{index}. {job['title']} - {job['company']}",
                    f"   Score: {job['score']}/10",
                    f"   URL: {job['url']}",
                ]
            )

    if health:
        lines.extend(["", "Collector health (today's runs):"])
        for entry in health:
            if entry["status"] == "error":
                lines.append(f"[FAILED] {entry['source']}: {entry['error_message']}")
            elif entry["status"] == "warning":
                lines.append(
                    f"[WARN 0 jobs] {entry['source']}: returned no jobs "
                    "despite recent successful runs"
                )
            else:
                lines.append(
                    f"[OK] {entry['source']}: {entry['jobs_found']} found, "
                    f"{entry['jobs_inserted']} new"
                )

    return "\n".join(lines)


def _get_collection_health() -> list[dict[str, str | int | None]]:
    connection = connect(_get_db_path())
    init_db(connection)
    rows = connection.execute(
        """
        SELECT source, status, jobs_found, jobs_inserted, error_message
        FROM collection_runs
        WHERE started_at >= date('now')
        ORDER BY source, started_at
        """
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def _get_top_scoring_jobs() -> list[dict[str, str | int | None]]:
    connection = connect(_get_db_path())
    init_db(connection)
    rows = connection.execute(
        """
        SELECT title, company, score, url
        FROM jobs
        WHERE score IS NOT NULL
        ORDER BY score DESC, datetime(date_collected) DESC, id DESC
        LIMIT 5
        """
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def _get_db_path() -> Path:
    if not CONFIG_PATH.exists():
        return ROOT_DIR / "jobscout.sqlite3"

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    db_path = config.get("database", {}).get("path", "jobscout.sqlite3")
    return ROOT_DIR / db_path


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if logger:
        logger(message)
    else:
        print(message)
