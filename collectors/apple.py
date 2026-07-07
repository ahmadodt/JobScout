from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import Job, clean_text, utc_now_iso
from collectors.http_base import HttpCollectorBase


SEARCH_URL = "https://jobs.apple.com/en-us/search?search={keyword}&location=germany-DEU"
DETAILS_URL = "https://jobs.apple.com/en-us/details/{position_id}"
# The search page server-renders its React Router state; results live in
# loaderData.search.searchResults.
HYDRATION_PATTERN = re.compile(
    r'window\.__staticRouterHydrationData = JSON\.parse\("(.*?)"\);', re.S
)


class AppleCollector(HttpCollectorBase):
    name = "apple"
    company = "Apple"

    def fetch_jobs(self) -> list[Job]:
        collected_at = utc_now_iso()
        jobs: list[Job] = []

        for keyword in self.keywords:
            html = self._get_html(SEARCH_URL.format(keyword=keyword))
            for entry in self._parse_search_results(html):
                position_id = str(entry.get("positionId") or entry.get("id", "")).split("-")[0]
                if not position_id:
                    continue

                locations = entry.get("locations") or []
                location = "; ".join(
                    clean_text(loc.get("name", "")) for loc in locations if loc.get("name")
                )
                post_date = entry.get("postDateInGMT") or entry.get("postingDate")

                jobs.append(
                    Job(
                        title=clean_text(
                            entry.get("postingTitle") or entry.get("transformedPostingTitle", "")
                        ),
                        company=self.company,
                        location=location,
                        source=self.name,
                        url=DETAILS_URL.format(position_id=position_id),
                        description=clean_text(entry.get("jobSummary", "")),
                        date_posted=str(post_date)[:10] if post_date else None,
                        date_collected=collected_at,
                    )
                )

        return jobs

    def _parse_search_results(self, html: str) -> list[dict]:
        match = HYDRATION_PATTERN.search(html)
        if not match:
            self.logger.warning("hydration data not found on Apple search page")
            return []
        try:
            unescaped = json.loads(f'"{match.group(1)}"')
            state = json.loads(unescaped)
        except (json.JSONDecodeError, ValueError):
            self.logger.warning("failed to parse Apple hydration data", exc_info=True)
            return []
        return state.get("loaderData", {}).get("search", {}).get("searchResults") or []


if __name__ == "__main__":
    collector = AppleCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.location} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
