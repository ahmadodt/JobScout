"""Manual verification harness: run one collector (or all) without touching the DB.

Usage:
    python run_collector_check.py amazon [--filter] [--max-pages 2] [--timeout-ms 30000]
    python run_collector_check.py --all

Exit code 1 if any checked collector returns zero jobs.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from collectors.registry import AVAILABLE_COLLECTORS, build_collectors
from services.config import load_config


def check_collector(name: str, collector) -> bool:
    print(f"\n=== {name} ===")
    started = time.monotonic()
    try:
        jobs = collector.collect()
    except Exception as exc:
        print(f"FAILED after {time.monotonic() - started:.1f}s: {type(exc).__name__}: {exc}")
        return False
    elapsed = time.monotonic() - started

    print(f"{len(jobs)} jobs in {elapsed:.1f}s")
    for job in jobs[:10]:
        print(f"  {job.title} | {job.location} | {job.date_posted or '-'} | {job.url}")
    if len(jobs) > 10:
        print(f"  ... and {len(jobs) - 10} more")

    if jobs:
        missing_location = sum(1 for job in jobs if not job.location)
        missing_date = sum(1 for job in jobs if not job.date_posted)
        short_description = sum(1 for job in jobs if len(job.description) < 200)
        print(
            f"field quality: {missing_location}/{len(jobs)} missing location, "
            f"{missing_date}/{len(jobs)} missing date_posted, "
            f"{short_description}/{len(jobs)} with description < 200 chars"
        )
        return True

    print("WARNING: zero jobs - collector may be broken or blocked")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?", help="Collector name (see config.yaml)")
    parser.add_argument("--all", action="store_true", help="Check every enabled collector")
    parser.add_argument(
        "--filter",
        action="store_true",
        help="Apply keyword filtering (off by default so raw scraping is visible)",
    )
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--timeout-ms", type=int, default=None)
    args = parser.parse_args()

    if not args.all and not args.name:
        parser.error("give a collector name or --all")

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    config = load_config()
    if args.max_pages is not None or args.timeout_ms is not None:
        for collector_config in config.get("collectors", {}).values():
            if not isinstance(collector_config, dict):
                continue
            if args.max_pages is not None:
                collector_config["max_pages"] = args.max_pages
            if args.timeout_ms is not None:
                collector_config["timeout_ms"] = args.timeout_ms

    if args.all:
        candidates = build_collectors(config)
    else:
        # Force-enable the requested collector so disabled ones can be diagnosed.
        target = args.name
        platform = target.split("_", 1)[0]
        if target in AVAILABLE_COLLECTORS:
            config.setdefault("collectors", {}).setdefault(target, {})["enabled"] = True
        elif platform in ("greenhouse", "lever", "ashby"):
            config.setdefault("collectors", {}).setdefault(platform, {})["enabled"] = True
        candidates = [
            (name, collector)
            for name, collector in build_collectors(config)
            if name == target
        ]
        if not candidates:
            known = ", ".join(sorted(AVAILABLE_COLLECTORS))
            print(f"Unknown collector '{target}'. Known single collectors: {known}")
            print("Board collectors use names like greenhouse_<slug>, lever_<slug>, ashby_<slug>.")
            sys.exit(2)

    for _, collector in candidates:
        collector.filter_keywords = args.filter

    all_ok = True
    for name, collector in candidates:
        if not check_collector(name, collector):
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
