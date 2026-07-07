from __future__ import annotations

from datetime import date, timedelta

from collectors.base import Job, utc_now_iso
from run_collection import _is_within_lookback, collect_all
from services.job_store import JobStore
from services.run_tracker import RunTracker


def _make_job(title: str, company: str = "TestCo", date_posted: str | None = None) -> Job:
    return Job(
        title=title,
        company=company,
        location="Munich, Germany",
        source="fake",
        url=f"https://example.com/jobs/{title.lower().replace(' ', '-')}",
        description="LLM work",
        date_posted=date_posted,
        date_collected=utc_now_iso(),
    )


class GoodCollector:
    name = "good"

    def collect(self) -> list[Job]:
        return [_make_job("LLM Engineer"), _make_job("RAG Specialist")]


class ExplodingCollector:
    name = "exploding"

    def collect(self) -> list[Job]:
        raise RuntimeError("site changed")


class EmptyCollector:
    name = "empty"

    def collect(self) -> list[Job]:
        return []


def _run(db_connection, collectors):
    store = JobStore(db_connection)
    tracker = RunTracker(db_connection)
    cutoff = date.today() - timedelta(days=30)
    totals = collect_all(collectors, store, tracker, cutoff, 30)
    return store, tracker, totals


def test_failure_does_not_abort_other_collectors(db_connection):
    collectors = [("exploding", ExplodingCollector()), ("good", GoodCollector())]

    store, tracker, (collected, new, skipped) = _run(db_connection, collectors)

    assert collected == 2
    assert new == 2
    runs = {row["source"]: row for row in tracker.latest_run_per_source()}
    assert runs["exploding"]["status"] == "error"
    assert "RuntimeError: site changed" in runs["exploding"]["error_message"]
    assert runs["good"]["status"] == "ok"
    assert runs["good"]["jobs_inserted"] == 2


def test_disabled_collectors_are_not_built():
    from collectors.registry import build_collectors

    config = {
        "collectors": {"mock": {"enabled": False}},
        "collection": {"keywords": ["llm"]},
    }
    assert build_collectors(config) == []


def test_enabled_collector_is_built_from_config():
    from collectors.mock import MockCollector
    from collectors.registry import build_collectors

    config = {
        "collectors": {"mock": {"enabled": True}},
        "collection": {"keywords": ["llm"]},
    }
    built = build_collectors(config)
    assert len(built) == 1
    assert built[0][0] == "mock"
    assert isinstance(built[0][1], MockCollector)


def test_zero_jobs_warns_only_after_previous_success(db_connection):
    collectors = [("empty", EmptyCollector())]

    # First-ever empty run: no history, so status is ok.
    _, tracker, _ = _run(db_connection, collectors)
    assert tracker.latest_run_per_source()[0]["status"] == "ok"

    # Seed a successful run, then an empty run should warn.
    run_id = tracker.start_run("empty")
    tracker.finish_run(run_id, "ok", jobs_found=5, jobs_inserted=5)
    _run(db_connection, collectors)
    assert tracker.latest_run_per_source()[0]["status"] == "warning"


def test_lookback_filter_skips_old_jobs(db_connection):
    old_date = (date.today() - timedelta(days=90)).isoformat()

    class OldJobsCollector:
        name = "old"

        def collect(self) -> list[Job]:
            return [
                _make_job("Old LLM Role", date_posted=old_date),
                _make_job("Fresh LLM Role", date_posted=date.today().isoformat()),
            ]

    store, _, (collected, new, skipped) = _run(
        db_connection, [("old", OldJobsCollector())]
    )

    assert collected == 2
    assert skipped == 1
    assert new == 1
    titles = [row["title"] for row in store.list_jobs()]
    assert titles == ["Fresh LLM Role"]


def test_is_within_lookback_permissive_on_missing_dates():
    cutoff = date.today() - timedelta(days=30)
    assert _is_within_lookback(None, cutoff) is True
    assert _is_within_lookback("not-a-date", cutoff) is True
    assert _is_within_lookback(date.today().isoformat(), cutoff) is True
    old = (date.today() - timedelta(days=60)).isoformat()
    assert _is_within_lookback(old, cutoff) is False
