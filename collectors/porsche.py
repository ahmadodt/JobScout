from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.browser_base import PlaywrightCollectorBase


PAGE_SIZE_SELECTOR = "select#paginationControl-bottom"


class PorscheCollector(PlaywrightCollectorBase):
    name = "porsche"
    company = "Porsche"
    search_url_templates = (
        "https://jobs.porsche.com/index.php?ac=search_result"
        "&search_criterion_keyword[]={keyword}"
        "&search_criterion_channel[]=12&search_criterion_country[]=46",
    )
    job_url_domains = ("jobs.porsche.com",)
    job_url_markers = ("ac=jobad", "job")
    content_wait_selectors = (
        "a[href*='ac=jobad']",
        "a[href*='job']",
        ".job a[href]",
        "[class*='job'] a[href]",
    )

    def after_search_load(self, page, timeout_error) -> None:
        # Instead of paginating, bump the results-per-page dropdown to 250.
        try:
            page.wait_for_selector(PAGE_SIZE_SELECTOR, timeout=self.timeout_ms)
            page.select_option(PAGE_SIZE_SELECTOR, value="250", timeout=self.timeout_ms)
            page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        except timeout_error:
            return


if __name__ == "__main__":
    collector = PorscheCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
