from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import Job, utc_now_iso


BMW_COMPANY = "BMW Group"
BMW_SOURCE = "bmw"
BMW_CAREERS_URL = "https://www.bmwgroup.jobs/en.html"
KEYWORDS = ("rag", "llm", "agent")
TARGET_LOCATIONS = ("germany", "deutschland", "münchen", "munich", "berlin", "frankfurt")


class BMWCollector:
    name = BMW_SOURCE

    def __init__(
        self,
        timeout_ms: int = 45000,
        filter_keywords: bool = True,
        max_age_days: int = 2,
    ):
        self.timeout_ms = timeout_ms
        self.filter_keywords = filter_keywords
        self.max_age_days = max_age_days

    def collect(self) -> list[Job]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "BMWCollector requires Playwright. Install it with "
                "`pip install playwright` and then run `playwright install chromium`."
            ) from exc

        collected_at = utc_now_iso()
        jobs: list[Job] = []
        seen_urls = set()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            detail_page = browser.new_page()

            try:
                page.goto(BMW_CAREERS_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
                self._wait_for_job_content(page, PlaywrightTimeoutError)

                previous_count = 0
                while True:
                    listings = self._extract_listing_links(page)
                    current_batch = (
                        listings[previous_count:] if len(listings) > previous_count else listings
                    )
                    should_stop = bool(current_batch) and self._oldest_job_is_too_old(current_batch)

                    self._collect_listing_batch(
                        current_batch,
                        detail_page,
                        collected_at,
                        jobs,
                        seen_urls,
                    )

                    if should_stop:
                        break

                    load_more = self._load_more_button(page)
                    if not load_more:
                        break

                    previous_count = len(listings)

                    try:
                        load_more.click(timeout=self.timeout_ms)
                        page.wait_for_function(
                            """
                            (previousCount) =>
                                document.querySelectorAll("a[href*='/jobfinder/job-description']").length > previousCount
                            """,
                            arg=previous_count,
                            timeout=self.timeout_ms,
                        )
                    except PlaywrightTimeoutError:
                        break
            except Exception:
                return self._dedupe_by_url(jobs)
            finally:
                browser.close()

        return self._dedupe_by_url(jobs)

    def _wait_for_job_content(self, page, timeout_error) -> None:
        selectors = [
            "a[href*='job']",
            "a[href*='jobs']",
            "[class*='jobfinder'] a[href]",
            "[class*='job'] a[href]",
        ]

        for selector in selectors:
            try:
                page.wait_for_selector(selector, timeout=self.timeout_ms)
                return
            except timeout_error:
                continue

    def _collect_listing_batch(
        self,
        listings: list[dict[str, str | None]],
        detail_page,
        collected_at: str,
        jobs: list[Job],
        seen_urls: set[str],
    ) -> None:
        for listing in self._recent_listings(listings):
            url = listing["url"]
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            if not self._is_target_location(listing["location"]):
                continue

            detail = self._extract_detail_page(detail_page, url)
            if not detail:
                continue

            description = detail["description"]
            if self.filter_keywords and not self._contains_keyword(description):
                continue

            jobs.append(
                Job(
                    title=detail["title"] or listing["title"],
                    company=BMW_COMPANY,
                    location=detail["location"] or listing["location"],
                    source=self.name,
                    url=url,
                    description=description,
                    date_posted=detail["date_posted"] or listing["date_posted"],
                    date_collected=collected_at,
                )
            )

    @staticmethod
    def _load_more_button(page):
        button = page.locator("div.grp-jobfinder-load-more button.cmp-button")
        if button.is_visible():
            return button
        return None

    def _extract_listing_links(self, page) -> list[dict[str, str]]:
        links = page.locator("a[href]").evaluate_all(
            """
            (anchors) => anchors.map((anchor) => {
                const container = anchor.closest("article, li, tr, div") || anchor;
                return {
                    title: (anchor.innerText || anchor.textContent || "").trim(),
                    url: anchor.href,
                    location: (container.innerText || "").trim()
                };
            })
            """
        )

        listings = []
        seen_urls = set()

        for link in links:
            url = urljoin(BMW_CAREERS_URL, link.get("url", ""))
            title = self._clean_text(link.get("title", ""))
            raw_listing_text = link.get("location", "")
            listing_text = self._clean_text(raw_listing_text)
            location = self._extract_location(raw_listing_text)
            date_posted = self._extract_date_posted(listing_text)

            if not self._looks_like_job_url(url, title):
                continue
            if url in seen_urls:
                continue

            listings.append(
                {
                    "title": title,
                    "url": url,
                    "location": location,
                    "date_posted": date_posted,
                }
            )
            seen_urls.add(url)

        return listings

    def _extract_detail_page(self, page, url: str) -> dict[str, str | None] | None:
        detail_timeout_ms = min(self.timeout_ms, 10000)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=detail_timeout_ms)
            page.wait_for_selector("body", timeout=detail_timeout_ms)
        except Exception:
            return None

        detail = page.evaluate(
            """
            () => {
                const body = document.body;
                const content =
                    document.querySelector("[class*='jobdescription']") ||
                    document.querySelector("[class*='job-description']") ||
                    document.querySelector("[class*='jobdetail']") ||
                    document.querySelector("[class*='job-detail']") ||
                    document.querySelector("main") ||
                    document.querySelector("article") ||
                    body;
                const heading = content.querySelector("h1, h2") || document.querySelector("h1, h2");
                return {
                    title: heading ? heading.innerText.trim() : "",
                    description: content.innerText.trim(),
                    location: content.innerText.trim(),
                };
            }
            """
        )

        description = self._clean_text(detail.get("description", ""))
        return {
            "title": self._clean_text(detail.get("title", "")),
            "location": self._extract_location(self._clean_text(detail.get("location", ""))),
            "description": description,
            "date_posted": self._extract_date_posted(description),
        }

    @staticmethod
    def _contains_keyword(text: str) -> bool:
        return any(
            re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text, re.IGNORECASE)
            for keyword in KEYWORDS
        )

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _is_target_location(location: str | None) -> bool:
        lower_location = (location or "").lower()
        return any(target in lower_location for target in TARGET_LOCATIONS)

    @staticmethod
    def _looks_like_job_url(url: str, title: str) -> bool:
        lower_url = url.lower()
        lower_title = title.lower()

        if not title or len(title) < 4:
            return False
        if "bmwgroup.jobs" not in lower_url and "successfactors" not in lower_url:
            return False
        if any(skip in lower_url for skip in ("login", "linkedin", "instagram", "youtube")):
            return False
        if lower_title in {"all jobs", "favourite jobs", "job finder"}:
            return False
        if "bmwgroup.jobs" in lower_url:
            return "/jobfinder/job-description" in lower_url

        return "job" in lower_url

    @staticmethod
    def _extract_location(text: str) -> str:
        clean_text = " ".join(text.split())
        labels = ("Location", "Standort", "City", "Ort")
        for label in labels:
            marker = f"{label}:"
            if marker.lower() in clean_text.lower():
                start = clean_text.lower().find(marker.lower()) + len(marker)
                return clean_text[start:].split("|", 1)[0].strip()

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            return lines[-1]

        return ""

    @staticmethod
    def _extract_date_posted(description: str) -> str | None:
        labels = ("Date Posted:", "Posted:", "Publication Date:", "Published:")
        lower_description = description.lower()
        for label in labels:
            marker = label.lower()
            if marker not in lower_description:
                continue
            start = lower_description.find(marker) + len(marker)
            value = description[start:].strip().split(" ", 1)[0]
            return value or None
        return None

    def _oldest_job_is_too_old(self, listings: list[dict[str, str | None]]) -> bool:
        parsed_dates = [
            parsed_date
            for listing in listings
            if (parsed_date := self._parse_date(listing.get("date_posted")))
        ]
        if not parsed_dates:
            return False

        return min(parsed_dates) < self._cutoff_date()

    def _recent_listings(self, listings: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
        return [
            listing
            for listing in listings
            if (posted_date := self._parse_date(listing.get("date_posted")))
            and posted_date >= self._cutoff_date()
        ]

    def _cutoff_date(self) -> date:
        return date.today() - timedelta(days=self.max_age_days)

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        if not value:
            return None

        for date_format in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue

        return None

    @staticmethod
    def _dedupe_by_url(jobs: list[Job]) -> list[Job]:
        deduped = []
        seen_urls = set()
        for job in jobs:
            if job.url in seen_urls:
                continue
            deduped.append(job)
            seen_urls.add(job.url)
        return deduped


if __name__ == "__main__":
    collector = BMWCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
