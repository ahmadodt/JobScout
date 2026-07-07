from __future__ import annotations

from collectors.ashby import AshbyCollector
from collectors.greenhouse import GreenhouseCollector
from collectors.lever import LeverCollector


GREENHOUSE_PAYLOAD = {
    "jobs": [
        {
            "title": "LLM Engineer",
            "absolute_url": "https://boards.greenhouse.io/testco/jobs/1",
            "location": {"name": "Berlin, Germany"},
            "updated_at": "2026-07-01T10:00:00-04:00",
            "content": "&lt;p&gt;Build &lt;b&gt;RAG&lt;/b&gt; systems.&lt;/p&gt;",
        },
        {
            "title": "Office Manager",
            "absolute_url": "https://boards.greenhouse.io/testco/jobs/2",
            "location": {"name": "New York, USA"},
            "updated_at": "2026-07-01T10:00:00-04:00",
            "content": "<p>Keep the office running.</p>",
        },
    ]
}

LEVER_PAYLOAD = [
    {
        "text": "Agent Platform Engineer",
        "hostedUrl": "https://jobs.lever.co/testco/abc",
        "categories": {"location": "Munich, Germany"},
        "createdAt": 1751328000000,  # 2025-07-01 UTC
        "descriptionPlain": "Work on agent orchestration.",
    },
    {
        "text": "Sales Lead",
        "hostedUrl": "https://jobs.lever.co/testco/def",
        "categories": {"location": "Paris, France"},
        "createdAt": 1751328000000,
        "descriptionPlain": "Sell things.",
    },
]

ASHBY_PAYLOAD = {
    "jobs": [
        {
            "title": "Research Engineer, LLM Inference",
            "jobUrl": "https://jobs.ashbyhq.com/testco/1",
            "location": "San Francisco",
            "secondaryLocations": [{"location": "London, UK"}],
            "isRemote": True,
            "publishedAt": "2026-06-20T00:00:00Z",
            "descriptionPlain": "Serve LLMs fast.",
        },
        {
            "title": "Recruiter",
            "jobUrl": "https://jobs.ashbyhq.com/testco/2",
            "location": "San Francisco",
            "secondaryLocations": [],
            "isRemote": False,
            "publishedAt": "2026-06-20T00:00:00Z",
            "descriptionPlain": "Hire people.",
        },
    ]
}


def _patch(collector, payload, monkeypatch):
    monkeypatch.setattr(collector, "_get_json", lambda url, params=None: payload)
    return collector


def test_greenhouse_maps_fields_and_filters_keywords(monkeypatch):
    collector = _patch(
        GreenhouseCollector("testco", "TestCo"), GREENHOUSE_PAYLOAD, monkeypatch
    )
    jobs = collector.collect()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "LLM Engineer"
    assert job.company == "TestCo"
    assert job.source == "greenhouse_testco"
    assert job.location == "Berlin, Germany"
    assert job.url == "https://boards.greenhouse.io/testco/jobs/1"
    assert job.date_posted == "2026-07-01"
    assert "Build RAG systems." in job.description
    assert "<" not in job.description  # HTML stripped


def test_greenhouse_location_allowlist(monkeypatch):
    collector = _patch(
        GreenhouseCollector("testco", "TestCo", locations=["new york"], filter_keywords=False),
        GREENHOUSE_PAYLOAD,
        monkeypatch,
    )
    jobs = collector.collect()
    assert [job.location for job in jobs] == ["New York, USA"]


def test_lever_maps_fields_and_filters_keywords(monkeypatch):
    collector = _patch(LeverCollector("testco", "TestCo"), LEVER_PAYLOAD, monkeypatch)
    jobs = collector.collect()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Agent Platform Engineer"
    assert job.source == "lever_testco"
    assert job.location == "Munich, Germany"
    assert job.date_posted == "2025-07-01"


def test_ashby_maps_fields_and_filters_keywords(monkeypatch):
    collector = _patch(AshbyCollector("testco", "TestCo"), ASHBY_PAYLOAD, monkeypatch)
    jobs = collector.collect()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Research Engineer, LLM Inference"
    assert job.source == "ashby_testco"
    assert job.location == "San Francisco; London, UK; Remote"
    assert job.date_posted == "2026-06-20"


def test_ashby_location_allowlist_covers_secondary_and_remote(monkeypatch):
    collector = _patch(
        AshbyCollector("testco", "TestCo", locations=["remote"], filter_keywords=False),
        ASHBY_PAYLOAD,
        monkeypatch,
    )
    jobs = collector.collect()
    assert len(jobs) == 1
    assert jobs[0].title == "Research Engineer, LLM Inference"


def test_registry_expands_boards():
    from collectors.registry import build_collectors

    config = {
        "collection": {"keywords": ["llm"]},
        "collectors": {
            "greenhouse": {
                "enabled": True,
                "boards": [{"slug": "testco", "company": "TestCo"}],
            },
            "lever": {"enabled": True, "boards": [{"slug": "other", "company": "Other"}]},
            "ashby": {"enabled": False, "boards": [{"slug": "nope", "company": "Nope"}]},
        },
    }
    built = dict(build_collectors(config))
    assert set(built) == {"greenhouse_testco", "lever_other"}
    assert built["greenhouse_testco"].keywords == ("llm",)
