from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.browser_base import PlaywrightCollectorBase


class MicrosoftGermanyCollector(PlaywrightCollectorBase):
    # jobs.microsoft.com is gone; the current SPA lives on jobs.careers.microsoft.com.
    name = "microsoft_germany"
    company = "Microsoft Germany"
    search_url_templates = (
        "https://jobs.careers.microsoft.com/global/en/search?q={keyword}&lc=Germany",
    )
    job_url_domains = ("careers.microsoft.com",)
    job_url_markers = ("/job/",)


if __name__ == "__main__":
    collector = MicrosoftGermanyCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
