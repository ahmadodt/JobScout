from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import DEFAULT_KEYWORDS, Job, clean_text, utc_now_iso
from collectors.http_base import HttpCollectorBase


JOB_BOARD_API_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


class AshbyCollector(HttpCollectorBase):
    """Collects jobs from an Ashby job board via the public posting API."""

    def __init__(
        self,
        slug: str,
        company: str,
        keywords: Sequence[str] = DEFAULT_KEYWORDS,
        locations: Sequence[str] | None = None,
        timeout_ms: int = 45000,
        filter_keywords: bool = True,
    ):
        self.name = f"ashby_{slug}"
        super().__init__(
            timeout_ms=timeout_ms, filter_keywords=filter_keywords, keywords=keywords
        )
        self.slug = slug
        self.company = company
        self.locations = tuple(loc.lower() for loc in locations) if locations else None

    def fetch_jobs(self) -> list[Job]:
        payload = self._get_json(
            JOB_BOARD_API_URL.format(slug=self.slug),
            params={"includeCompensation": "false"},
        )
        collected_at = utc_now_iso()
        jobs = []

        for entry in payload.get("jobs", []):
            location = self._combined_location(entry)
            if not self._matches_location(location):
                continue

            published_at = entry.get("publishedAt")
            jobs.append(
                Job(
                    title=clean_text(entry.get("title", "")),
                    company=self.company,
                    location=location,
                    source=self.name,
                    url=entry.get("jobUrl") or entry.get("applyUrl") or "",
                    description=clean_text(entry.get("descriptionPlain", "")),
                    date_posted=published_at[:10] if published_at else None,
                    date_collected=collected_at,
                )
            )

        return jobs

    @staticmethod
    def _combined_location(entry: dict) -> str:
        parts = [clean_text(entry.get("location", ""))]
        for secondary in entry.get("secondaryLocations") or []:
            parts.append(clean_text(secondary.get("location", "")))
        if entry.get("isRemote"):
            parts.append("Remote")
        return "; ".join(part for part in parts if part)

    def _matches_location(self, location: str) -> bool:
        if not self.locations:
            return True
        lower_location = location.lower()
        return any(target in lower_location for target in self.locations)


if __name__ == "__main__":
    slug_arg = sys.argv[1] if len(sys.argv) > 1 else "openai"
    collector = AshbyCollector(slug_arg, slug_arg.title(), filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.location} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
