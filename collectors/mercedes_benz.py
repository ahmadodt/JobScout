from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.browser_base import PlaywrightCollectorBase


class MercedesBenzCollector(PlaywrightCollectorBase):
    name = "mercedes_benz"
    company = "Mercedes-Benz"
    search_url_templates = (
        "https://jobs.mercedes-benz.com/en?search={keyword}",
    )
    job_url_domains = ("mercedes-benz.com", "jobs.mercedes-benz.com")


if __name__ == "__main__":
    collector = MercedesBenzCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
