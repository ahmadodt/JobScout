from __future__ import annotations

from collectors.base import Job, clean_text, contains_keyword, dedupe_by_url, utc_now_iso


def test_matches_whole_words_case_insensitive():
    assert contains_keyword("Building a RAG pipeline") is True
    assert contains_keyword("Senior LLM Engineer") is True
    assert contains_keyword("multi-agent systems") is True


def test_does_not_match_inside_other_words():
    assert contains_keyword("cloud storage engineer") is False  # 'rag' in 'storage'
    assert contains_keyword("Werbeagentur Berlin") is False  # 'agent' in 'Agentur'
    assert contains_keyword("Fullmetal Alchemist") is False


def test_custom_keywords():
    assert contains_keyword("GenAI platform team", keywords=("genai",)) is True
    assert contains_keyword("LLM Engineer", keywords=("genai",)) is False


def test_clean_text_collapses_whitespace():
    assert clean_text("  hello\n\tworld  ") == "hello world"
    assert clean_text(None) == ""


def _job(url: str) -> Job:
    return Job(
        title="LLM Engineer",
        company="TestCo",
        location="Berlin",
        source="test",
        url=url,
        description="",
        date_posted=None,
        date_collected=utc_now_iso(),
    )


def test_dedupe_by_url_keeps_first():
    jobs = [_job("https://a.example/1"), _job("https://a.example/1"), _job("https://a.example/2")]
    deduped = dedupe_by_url(jobs)
    assert [job.url for job in deduped] == ["https://a.example/1", "https://a.example/2"]
