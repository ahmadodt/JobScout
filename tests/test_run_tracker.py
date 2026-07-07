from __future__ import annotations

import pytest

from services.run_tracker import RunTracker


def test_start_run_creates_running_row(db_connection):
    tracker = RunTracker(db_connection)
    run_id = tracker.start_run("bmw")

    row = db_connection.execute(
        "SELECT * FROM collection_runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row["source"] == "bmw"
    assert row["status"] == "running"
    assert row["started_at"]
    assert row["finished_at"] is None


def test_finish_run_records_outcome(db_connection):
    tracker = RunTracker(db_connection)
    run_id = tracker.start_run("bmw")
    tracker.finish_run(run_id, "ok", jobs_found=5, jobs_inserted=2)

    row = db_connection.execute(
        "SELECT * FROM collection_runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row["status"] == "ok"
    assert row["jobs_found"] == 5
    assert row["jobs_inserted"] == 2
    assert row["finished_at"] is not None
    assert row["error_message"] is None


def test_finish_run_records_error(db_connection):
    tracker = RunTracker(db_connection)
    run_id = tracker.start_run("sap")
    tracker.finish_run(run_id, "error", error_message="RuntimeError: boom")

    row = db_connection.execute(
        "SELECT * FROM collection_runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row["status"] == "error"
    assert row["error_message"] == "RuntimeError: boom"


def test_finish_run_rejects_bad_status(db_connection):
    tracker = RunTracker(db_connection)
    run_id = tracker.start_run("sap")
    with pytest.raises(ValueError):
        tracker.finish_run(run_id, "exploded")


def test_latest_run_per_source(db_connection):
    tracker = RunTracker(db_connection)
    first = tracker.start_run("bmw")
    tracker.finish_run(first, "ok", jobs_found=3, jobs_inserted=3)
    second = tracker.start_run("bmw")
    tracker.finish_run(second, "error", error_message="broke")
    other = tracker.start_run("sap")
    tracker.finish_run(other, "ok", jobs_found=1, jobs_inserted=0)

    latest = {row["source"]: row for row in tracker.latest_run_per_source()}
    assert set(latest) == {"bmw", "sap"}
    assert latest["bmw"]["id"] == second
    assert latest["bmw"]["status"] == "error"
    assert latest["sap"]["status"] == "ok"


def test_had_jobs_recently(db_connection):
    tracker = RunTracker(db_connection)
    assert tracker.had_jobs_recently("bmw") is False

    run_id = tracker.start_run("bmw")
    tracker.finish_run(run_id, "ok", jobs_found=4, jobs_inserted=4)
    assert tracker.had_jobs_recently("bmw") is True

    # A still-running row is ignored.
    tracker.start_run("sap")
    assert tracker.had_jobs_recently("sap") is False


def test_had_jobs_recently_respects_window(db_connection):
    tracker = RunTracker(db_connection)
    old = tracker.start_run("bmw")
    tracker.finish_run(old, "ok", jobs_found=10, jobs_inserted=10)
    for _ in range(3):
        run_id = tracker.start_run("bmw")
        tracker.finish_run(run_id, "warning", jobs_found=0)

    assert tracker.had_jobs_recently("bmw", n_runs=3) is False
    assert tracker.had_jobs_recently("bmw", n_runs=4) is True
