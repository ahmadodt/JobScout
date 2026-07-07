from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence


DEFAULT_KEYWORDS = ("rag", "llm", "agent")


@dataclass(frozen=True)
class Job:
    title: str
    company: str
    location: str
    source: str
    url: str
    description: str
    date_posted: str | None
    date_collected: str


class Collector(Protocol):
    name: str

    def collect(self) -> list[Job]:
        ...


def utc_now_iso() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    return now.isoformat() + "Z"


def contains_keyword(text: str, keywords: Sequence[str] = DEFAULT_KEYWORDS) -> bool:
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text, re.IGNORECASE)
        for keyword in keywords
    )


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def dedupe_by_url(jobs: list[Job]) -> list[Job]:
    deduped = []
    seen_urls = set()
    for job in jobs:
        if job.url in seen_urls:
            continue
        deduped.append(job)
        seen_urls.add(job.url)
    return deduped
