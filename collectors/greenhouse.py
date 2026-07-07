from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import DEFAULT_KEYWORDS, Job, clean_text, utc_now_iso
from collectors.http_base import HttpCollectorBase


BOARD_API_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


class GreenhouseCollector(HttpCollectorBase):
    """Collects jobs from a Greenhouse job board via the public boards API."""

    def __init__(
        self,
        slug: str,
        company: str,
        keywords: Sequence[str] = DEFAULT_KEYWORDS,
        locations: Sequence[str] | None = None,
        timeout_ms: int = 45000,
        filter_keywords: bool = True,
    ):
        self.name = f"greenhouse_{slug}"
        super().__init__(
            timeout_ms=timeout_ms, filter_keywords=filter_keywords, keywords=keywords
        )
        self.slug = slug
        self.company = company
        self.locations = tuple(loc.lower() for loc in locations) if locations else None

    def fetch_jobs(self) -> list[Job]:
        payload = self._get_json(
            BOARD_API_URL.format(slug=self.slug), params={"content": "true"}
        )
        collected_at = utc_now_iso()
        jobs = []

        for entry in payload.get("jobs", []):
            location = clean_text((entry.get("location") or {}).get("name", ""))
            if not self._matches_location(location):
                continue

            description = self._strip_html(entry.get("content", ""))
            updated_at = entry.get("updated_at") or entry.get("first_published")
            jobs.append(
                Job(
                    title=clean_text(entry.get("title", "")),
                    company=self.company,
                    location=location,
                    source=self.name,
                    url=entry.get("absolute_url", ""),
                    description=description,
                    date_posted=updated_at[:10] if updated_at else None,
                    date_collected=collected_at,
                )
            )

        return jobs

    def _matches_location(self, location: str) -> bool:
        if not self.locations:
            return True
        lower_location = location.lower()
        return any(target in lower_location for target in self.locations)

    @staticmethod
    def _strip_html(content: str) -> str:
        if not content:
            return ""
        import html

        from bs4 import BeautifulSoup

        return clean_text(BeautifulSoup(html.unescape(content), "html.parser").get_text(" "))


if __name__ == "__main__":
    slug_arg = sys.argv[1] if len(sys.argv) > 1 else "anthropic"
    collector = GreenhouseCollector(slug_arg, slug_arg.title(), filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.location} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
