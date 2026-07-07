from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.browser_base import PlaywrightCollectorBase


class MetaCollector(PlaywrightCollectorBase):
    # Best effort: metacareers.com is heavily bot-protected and may yield zero.
    name = "meta"
    company = "Meta"
    search_url_templates = (
        "https://www.metacareers.com/jobs?q={keyword}&offices[0]=Germany",
    )
    job_url_domains = ("metacareers.com",)


if __name__ == "__main__":
    collector = MetaCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
