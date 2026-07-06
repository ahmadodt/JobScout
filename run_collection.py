from __future__ import annotations

from datetime import date, timedelta

from collectors.allianz import AllianzCollector
from collectors.amazon import AmazonCollector
from collectors.apple import AppleCollector
from collectors.bmw import BMWCollector
from collectors.google import GoogleCollector
from collectors.mercedes_benz import MercedesBenzCollector
from collectors.meta import MetaCollector
from collectors.microsoft_germany import MicrosoftGermanyCollector
from collectors.mock import MockCollector
from collectors.porsche import PorscheCollector
from collectors.sap import SAPCollector
from collectors.siemens import SiemensCollector
from collectors.volkswagen import VolkswagenCollector
from database.db import connect, init_db
from services.config import load_config, resolve_db_path
from services.job_store import JobStore


AVAILABLE_COLLECTORS = {
    "mock": MockCollector,
    "bmw": BMWCollector,
    "porsche": PorscheCollector,
    "mercedes_benz": MercedesBenzCollector,
    "volkswagen": VolkswagenCollector,
    "siemens": SiemensCollector,
    "sap": SAPCollector,
    "allianz": AllianzCollector,
    "microsoft_germany": MicrosoftGermanyCollector,
    "google": GoogleCollector,
    "meta": MetaCollector,
    "apple": AppleCollector,
    "amazon": AmazonCollector,
}


def _is_within_lookback(date_posted: str | None, cutoff: date) -> bool:
    if not date_posted:
        return True
    try:
        posted = date.fromisoformat(date_posted[:10])
    except ValueError:
        return True
    return posted >= cutoff


def main() -> None:
    config = load_config()
    collectors_config = config["collectors"]
    lookback_days = config["collection"]["lookback_days"]
    cutoff = date.today() - timedelta(days=lookback_days)

    connection = connect(resolve_db_path(config))
    init_db(connection)
    store = JobStore(connection)

    total_collected = 0
    total_new = 0
    total_skipped = 0

    for name, collector_class in AVAILABLE_COLLECTORS.items():
        collector_config = collectors_config.get(name, {})
        if not collector_config.get("enabled", False):
            continue

        collector = collector_class()
        jobs = collector.collect()
        recent_jobs = [job for job in jobs if _is_within_lookback(job.date_posted, cutoff)]
        skipped = len(jobs) - len(recent_jobs)
        new_count = store.insert_jobs(recent_jobs)

        total_collected += len(jobs)
        total_new += new_count
        total_skipped += skipped
        message = f"{name}: collected {len(jobs)} jobs, inserted {new_count} new jobs"
        if skipped:
            message += f", skipped {skipped} older than {lookback_days} days"
        print(message)

    print(f"Total collected: {total_collected}")
    print(f"Total skipped (older than {lookback_days} days): {total_skipped}")
    print(f"Total new: {total_new}")


if __name__ == "__main__":
    main()
