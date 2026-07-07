from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.successfactors import SuccessFactorsCollector


class SAPCollector(SuccessFactorsCollector):
    name = "sap"
    company = "SAP"
    base_url = "https://jobs.sap.com"
    search_params = {"locationsearch": "Germany"}


if __name__ == "__main__":
    collector = SAPCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.location} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
