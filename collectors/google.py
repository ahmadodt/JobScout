from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.browser_base import PlaywrightCollectorBase


class GoogleCollector(PlaywrightCollectorBase):
    # Best effort: Google Careers is heavily bot-protected and may yield zero.
    name = "google"
    company = "Google"
    search_url_templates = (
        "https://www.google.com/about/careers/applications/jobs/results?q={keyword}&location=Germany",
    )
    job_url_domains = ("google.com",)
    job_url_markers = ("jobs/results",)


if __name__ == "__main__":
    collector = GoogleCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
