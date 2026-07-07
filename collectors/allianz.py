from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.browser_base import PlaywrightCollectorBase


class AllianzCollector(PlaywrightCollectorBase):
    # careers.allianz.com dropped its SuccessFactors /search/ page mid-2026;
    # the new portal is a JS app, so this stays on Playwright.
    name = "allianz"
    company = "Allianz"
    search_url_templates = (
        "https://careers.allianz.com/global/en/search-results?keywords={keyword}",
    )
    job_url_domains = ("careers.allianz.com",)


if __name__ == "__main__":
    collector = AllianzCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
