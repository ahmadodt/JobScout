from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.browser_base import PlaywrightCollectorBase


class AppleCollector(PlaywrightCollectorBase):
    name = "apple"
    company = "Apple"
    search_url_templates = (
        "https://jobs.apple.com/en-us/search?search={keyword}&location=germany-DEU",
    )
    job_url_domains = ("jobs.apple.com",)
    job_url_markers = ("/details/", "job", "position")


if __name__ == "__main__":
    collector = AppleCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
