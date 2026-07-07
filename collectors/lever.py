from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import DEFAULT_KEYWORDS, Job, clean_text, utc_now_iso
from collectors.http_base import HttpCollectorBase


POSTINGS_API_URL = "https://api.lever.co/v0/postings/{slug}"


class LeverCollector(HttpCollectorBase):
    """Collects jobs from a Lever job board via the public postings API."""

    def __init__(
        self,
        slug: str,
        company: str,
        keywords: Sequence[str] = DEFAULT_KEYWORDS,
        locations: Sequence[str] | None = None,
        timeout_ms: int = 45000,
        filter_keywords: bool = True,
    ):
        self.name = f"lever_{slug}"
        super().__init__(
            timeout_ms=timeout_ms, filter_keywords=filter_keywords, keywords=keywords
        )
        self.slug = slug
        self.company = company
        self.locations = tuple(loc.lower() for loc in locations) if locations else None

    def fetch_jobs(self) -> list[Job]:
        payload = self._get_json(
            POSTINGS_API_URL.format(slug=self.slug), params={"mode": "json"}
        )
        collected_at = utc_now_iso()
        jobs = []

        for entry in payload:
            location = clean_text((entry.get("categories") or {}).get("location", ""))
            if not self._matches_location(location):
                continue

            created_at = entry.get("createdAt")
            date_posted = None
            if created_at:
                date_posted = (
                    datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                    .date()
                    .isoformat()
                )

            jobs.append(
                Job(
                    title=clean_text(entry.get("text", "")),
                    company=self.company,
                    location=location,
                    source=self.name,
                    url=entry.get("hostedUrl", ""),
                    description=clean_text(entry.get("descriptionPlain", "")),
                    date_posted=date_posted,
                    date_collected=collected_at,
                )
            )

        return jobs

    def _matches_location(self, location: str) -> bool:
        if not self.locations:
            return True
        lower_location = location.lower()
        return any(target in lower_location for target in self.locations)


if __name__ == "__main__":
    slug_arg = sys.argv[1] if len(sys.argv) > 1 else "mistral"
    collector = LeverCollector(slug_arg, slug_arg.title(), filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.location} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
