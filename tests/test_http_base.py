from __future__ import annotations

import requests

from collectors.base import Job, utc_now_iso
from collectors.http_base import HttpCollectorBase


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def _collector(monkeypatch, responses):
    collector = HttpCollectorBase()
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(collector.session, "get", fake_get)
    monkeypatch.setattr("collectors.http_base.time.sleep", lambda _: None)
    return collector, calls


def test_get_json_success(monkeypatch):
    collector, calls = _collector(monkeypatch, [FakeResponse(json_data={"jobs": []})])
    assert collector._get_json("https://api.example/jobs") == {"jobs": []}
    assert len(calls) == 1


def test_retries_once_on_timeout(monkeypatch):
    collector, calls = _collector(
        monkeypatch,
        [requests.Timeout("slow"), FakeResponse(json_data={"ok": True})],
    )
    assert collector._get_json("https://api.example/jobs") == {"ok": True}
    assert len(calls) == 2


def test_retries_once_on_server_error(monkeypatch):
    collector, calls = _collector(
        monkeypatch,
        [FakeResponse(status_code=503), FakeResponse(json_data={"ok": True})],
    )
    assert collector._get_json("https://api.example/jobs") == {"ok": True}
    assert len(calls) == 2


def test_gives_up_after_second_timeout(monkeypatch):
    collector, calls = _collector(
        monkeypatch, [requests.Timeout("slow"), requests.Timeout("slow again")]
    )
    try:
        collector._get_json("https://api.example/jobs")
        assert False, "expected Timeout"
    except requests.Timeout:
        pass
    assert len(calls) == 2


def test_collect_applies_keyword_filter():
    class FakeCollector(HttpCollectorBase):
        name = "fake"
        company = "FakeCo"

        def fetch_jobs(self):
            def job(title):
                return Job(
                    title=title,
                    company=self.company,
                    location="Berlin",
                    source=self.name,
                    url=f"https://example.com/{title}",
                    description="",
                    date_posted=None,
                    date_collected=utc_now_iso(),
                )

            return [job("LLM Engineer"), job("Bakery Manager")]

    assert [j.title for j in FakeCollector().collect()] == ["LLM Engineer"]
    assert len(FakeCollector(filter_keywords=False).collect()) == 2
