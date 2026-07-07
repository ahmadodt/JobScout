from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import DEFAULT_KEYWORDS
from collectors.browser_base import PlaywrightCollectorBase


TARGET_LOCATIONS = ("germany", "deutschland", "münchen", "munich", "berlin", "frankfurt")
LOAD_MORE_SELECTOR = "div.grp-jobfinder-load-more button.cmp-button"
JOB_LINK_SELECTOR = "a[href*='/jobfinder/job-description']"


class BMWCollector(PlaywrightCollectorBase):
    name = "bmw"
    company = "BMW Group"
    search_urls = ("https://www.bmwgroup.jobs/en.html",)
    job_url_domains = ("bmwgroup.jobs", "successfactors")
    title_blocklist = frozenset({"all jobs", "favourite jobs", "job finder"})
    content_wait_selectors = (
        "a[href*='job']",
        "a[href*='jobs']",
        "[class*='jobfinder'] a[href]",
        "[class*='job'] a[href]",
    )
    detail_timeout_cap_ms = 10000

    def __init__(
        self,
        timeout_ms: int = 45000,
        filter_keywords: bool = True,
        keywords: Sequence[str] = DEFAULT_KEYWORDS,
        max_pages: int = 50,
        max_age_days: int = 2,
    ):
        super().__init__(
            timeout_ms=timeout_ms,
            filter_keywords=filter_keywords,
            keywords=keywords,
            max_pages=max_pages,
        )
        self.max_age_days = max_age_days
        self._previous_link_count = 0

    def looks_like_job_url(self, url: str, title: str) -> bool:
        if not super().looks_like_job_url(url, title):
            return False
        if "bmwgroup.jobs" in url.lower():
            return "/jobfinder/job-description" in url.lower()
        return True

    def accept_listing(self, listing: dict[str, str | None]) -> bool:
        posted = self._parse_date(listing.get("date_posted"))
        if not posted or posted < self._cutoff_date():
            return False
        location = (listing.get("location") or "").lower()
        return any(target in location for target in TARGET_LOCATIONS)

    def should_stop_paginating(self, listings: list[dict[str, str | None]]) -> bool:
        parsed_dates = [
            parsed
            for listing in listings[self._previous_link_count:] or listings
            if (parsed := self._parse_date(listing.get("date_posted")))
        ]
        return bool(parsed_dates) and min(parsed_dates) < self._cutoff_date()

    def paginate(self, page, timeout_error) -> bool:
        button = page.locator(LOAD_MORE_SELECTOR)
        if not button.is_visible():
            return False

        self._previous_link_count = page.locator(JOB_LINK_SELECTOR).count()
        try:
            button.click(timeout=self.timeout_ms)
            page.wait_for_function(
                "(previousCount) =>"
                f" document.querySelectorAll(\"{JOB_LINK_SELECTOR}\").length > previousCount",
                arg=self._previous_link_count,
                timeout=self.timeout_ms,
            )
        except timeout_error:
            return False
        return True

    def _cutoff_date(self) -> date:
        return date.today() - timedelta(days=self.max_age_days)


if __name__ == "__main__":
    collector = BMWCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
