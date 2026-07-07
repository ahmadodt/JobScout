from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import Job, clean_text, utc_now_iso
from collectors.http_base import HttpCollectorBase


# careers.allianz.com is a Phenom People site; search results are embedded
# server-side in phApp.ddo.eagerLoadRefineSearch.data.jobs.
SEARCH_URL = "https://careers.allianz.com/global/en/search-results?keywords={keyword}"
JOB_URL = "https://careers.allianz.com/global/en/job/{job_id}"
DDO_PATTERN = re.compile(r"phApp\.ddo\s*=\s*(\{.*?\});", re.S)


class AllianzCollector(HttpCollectorBase):
    name = "allianz"
    company = "Allianz"

    def fetch_jobs(self) -> list[Job]:
        collected_at = utc_now_iso()
        jobs: list[Job] = []

        for keyword in self.keywords:
            html = self._get_html(SEARCH_URL.format(keyword=keyword))
            for entry in self._parse_embedded_jobs(html):
                job_id = entry.get("jobId") or entry.get("reqId")
                if not job_id:
                    continue

                posted = entry.get("postedDate") or entry.get("dateCreated")
                jobs.append(
                    Job(
                        title=clean_text(entry.get("title", "")),
                        company=self.company,
                        location=clean_text(
                            entry.get("cityStateCountry") or entry.get("location", "")
                        ),
                        source=self.name,
                        url=entry.get("applyUrl") or JOB_URL.format(job_id=job_id),
                        description=clean_text(entry.get("descriptionTeaser", "")),
                        date_posted=str(posted)[:10] if posted else None,
                        date_collected=collected_at,
                    )
                )

        return jobs

    def _parse_embedded_jobs(self, html: str) -> list[dict]:
        match = DDO_PATTERN.search(html)
        if not match:
            self.logger.warning("phApp.ddo not found on Allianz search page")
            return []
        try:
            ddo = json.loads(match.group(1))
        except json.JSONDecodeError:
            self.logger.warning("failed to parse Allianz phApp.ddo", exc_info=True)
            return []
        return (
            ddo.get("eagerLoadRefineSearch", {}).get("data", {}).get("jobs") or []
        )


if __name__ == "__main__":
    collector = AllianzCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.location} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
