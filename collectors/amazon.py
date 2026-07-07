from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import DEFAULT_KEYWORDS, Job, clean_text, utc_now_iso
from collectors.http_base import HttpCollectorBase


SEARCH_API_URL = "https://www.amazon.jobs/en/search.json"
BASE_URL = "https://www.amazon.jobs"
RESULTS_PER_PAGE = 100
# ISO 3166-1 alpha-3, as used by the normalized_country_code facet.
TARGET_COUNTRY_CODES = ("DEU",)


class AmazonCollector(HttpCollectorBase):
    name = "amazon"
    company = "Amazon"

    def __init__(
        self,
        timeout_ms: int = 45000,
        filter_keywords: bool = True,
        keywords: Sequence[str] = DEFAULT_KEYWORDS,
        max_pages: int = 3,
        country_codes: Sequence[str] = TARGET_COUNTRY_CODES,
    ):
        super().__init__(
            timeout_ms=timeout_ms,
            filter_keywords=filter_keywords,
            keywords=keywords,
            max_pages=max_pages,
        )
        self.country_codes = tuple(code.upper() for code in country_codes)

    def fetch_jobs(self) -> list[Job]:
        collected_at = utc_now_iso()
        jobs: list[Job] = []

        for keyword in self.keywords:
            for country_code in self.country_codes:
                for page in range(self.max_pages):
                    payload = self._get_json(
                        SEARCH_API_URL,
                        params={
                            "base_query": keyword,
                            "normalized_country_code[]": country_code,
                            "result_limit": RESULTS_PER_PAGE,
                            "offset": page * RESULTS_PER_PAGE,
                        },
                    )
                    entries = payload.get("jobs") or []
                    if not entries:
                        break

                    for entry in entries:
                        jobs.append(self._to_job(entry, collected_at))

                    if len(entries) < RESULTS_PER_PAGE:
                        break

        return jobs

    def _to_job(self, entry: dict, collected_at: str) -> Job:
        description = clean_text(
            " ".join(
                entry.get(field) or ""
                for field in ("description", "basic_qualifications", "preferred_qualifications")
            )
        )
        return Job(
            title=clean_text(entry.get("title", "")),
            company=self.company,
            location=clean_text(entry.get("normalized_location") or entry.get("location", "")),
            source=self.name,
            url=BASE_URL + entry.get("job_path", ""),
            description=description,
            date_posted=self._parse_posted_date(entry.get("posted_date")),
            date_collected=collected_at,
        )

    @staticmethod
    def _parse_posted_date(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%B %d, %Y").date().isoformat()
        except ValueError:
            return None


if __name__ == "__main__":
    collector = AmazonCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.location} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
