from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import Job, utc_now_iso


BMW_COMPANY = "BMW Group"
BMW_SOURCE = "bmw"
BMW_CAREERS_URL = "https://www.bmwgroup.jobs/en.html"
KEYWORDS = ("rag", "llm", "agent")


class BMWCollector:
    name = BMW_SOURCE

    def __init__(self, timeout_ms: int = 45000, filter_keywords: bool = True):
        self.timeout_ms = timeout_ms
        self.filter_keywords = filter_keywords

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

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(BMW_CAREERS_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
            self._wait_for_job_content(page, PlaywrightTimeoutError)

            listing_links = self._extract_listing_links(page)
            jobs = []

            for listing in listing_links:
                detail = self._extract_detail_page(page, listing["url"])
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
                        url=listing["url"],
                        description=description,
                        date_posted=detail["date_posted"],
                        date_collected=collected_at,
                    )
                )

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
            location = self._extract_location(self._clean_text(link.get("location", "")))

            if not self._looks_like_job_url(url, title):
                continue
            if url in seen_urls:
                continue

            listings.append({"title": title, "url": url, "location": location})
            seen_urls.add(url)

        return listings

    def _extract_detail_page(self, page, url: str) -> dict[str, str | None] | None:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
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
        labels = ("Location", "Standort", "City", "Ort")
        for label in labels:
            marker = f"{label}:"
            if marker.lower() in text.lower():
                start = text.lower().find(marker.lower()) + len(marker)
                return text[start:].split("|", 1)[0].strip()
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
