from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import Job, utc_now_iso


MERCEDES_BENZ_COMPANY = "Mercedes-Benz"
MERCEDES_BENZ_SOURCE = "mercedes_benz"
MERCEDES_BENZ_CAREERS_URL = "https://www.mercedes-benz.com/en/career/"
MERCEDES_BENZ_SEARCH_URLS = (
    "https://jobs.mercedes-benz.com/en?search=agent",
    "https://jobs.mercedes-benz.com/en?search=llm",
    "https://jobs.mercedes-benz.com/en?search=rag",
    "https://www.mercedes-benz.com/en/career/",
)
MERCEDES_BENZ_JOB_DOMAINS = ('mercedes-benz.com', 'jobs.mercedes-benz.com')
KEYWORDS = ("rag", "llm", "agent")


class MercedesBenzCollector:
    name = MERCEDES_BENZ_SOURCE

    def __init__(self, timeout_ms: int = 45000, filter_keywords: bool = True):
        self.timeout_ms = timeout_ms
        self.filter_keywords = filter_keywords

    def collect(self) -> list[Job]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "MercedesBenzCollector requires Playwright. Install it with "
                "`pip install playwright` and then run `playwright install chromium`."
            ) from exc

        collected_at = utc_now_iso()
        jobs: list[Job] = []
        seen_urls: set[str] = set()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            detail_page = browser.new_page()

            for search_url in MERCEDES_BENZ_SEARCH_URLS:
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    self._wait_for_job_content(page, PlaywrightTimeoutError)
                except Exception:
                    continue

                for listing in self._extract_listing_links(page, search_url):
                    url = listing["url"]
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    detail = self._extract_detail_page(detail_page, url)
                    if not detail:
                        continue

                    description = detail["description"]
                    combined_text = " ".join(
                        part or ""
                        for part in (
                            detail["title"],
                            detail["location"],
                            description,
                        )
                    )
                    if self.filter_keywords and not self._contains_keyword(combined_text):
                        continue

                    jobs.append(
                        Job(
                            title=detail["title"] or listing["title"],
                            company=MERCEDES_BENZ_COMPANY,
                            location=detail["location"] or listing["location"],
                            source=self.name,
                            url=url,
                            description=description,
                            date_posted=detail["date_posted"] or listing["date_posted"],
                            date_collected=collected_at,
                        )
                    )

            browser.close()

        return self._dedupe_by_url(jobs)

    def _wait_for_job_content(self, page, timeout_error) -> None:
        selectors = [
            "a[href*='job']",
            "a[href*='career']",
            "[class*='job'] a[href]",
            "[class*='career'] a[href]",
            "[data-testid*='job'] a[href]",
        ]

        for selector in selectors:
            try:
                page.wait_for_selector(selector, timeout=self.timeout_ms)
                return
            except timeout_error:
                continue

    def _extract_listing_links(self, page, base_url: str) -> list[dict[str, str | None]]:
        links = page.locator("a[href]").evaluate_all(
            """
            (anchors) => anchors.map((anchor) => {
                const container =
                    anchor.closest("article, li, tr, [role='listitem'], [data-testid*='job'], .job, [class*='job'], [class*='result'], [class*='card']") ||
                    anchor;
                return {
                    title: (anchor.innerText || anchor.textContent || "").trim(),
                    url: anchor.href || anchor.getAttribute("href") || "",
                    text: (container.innerText || "").trim()
                };
            })
            """
        )

        listings = []
        seen_urls = set()

        for link in links:
            url = urljoin(base_url, link.get("url", ""))
            title = self._clean_text(link.get("title", ""))
            listing_text = self._clean_text(link.get("text", ""))

            if not self._looks_like_job_url(url, title):
                continue
            if url in seen_urls:
                continue

            listings.append(
                {
                    "title": title,
                    "url": url,
                    "location": self._extract_location(listing_text),
                    "date_posted": self._extract_date_posted(listing_text),
                }
            )
            seen_urls.add(url)

        return listings

    def _extract_detail_page(self, page, url: str) -> dict[str, str | None] | None:
        detail_timeout_ms = min(self.timeout_ms, 15000)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=detail_timeout_ms)
            page.wait_for_selector("body", timeout=detail_timeout_ms)
        except Exception:
            return None

        detail = page.evaluate(
            """
            () => {
                const content =
                    document.querySelector("[class*='jobdetail']") ||
                    document.querySelector("[class*='job-detail']") ||
                    document.querySelector("[class*='jobDescription']") ||
                    document.querySelector("[class*='job-description']") ||
                    document.querySelector("[data-testid*='job']") ||
                    document.querySelector("main") ||
                    document.querySelector("article") ||
                    document.body;
                const heading = content.querySelector("h1, h2") || document.querySelector("h1, h2");
                return {
                    title: heading ? heading.innerText.trim() : "",
                    description: content.innerText.trim(),
                    text: content.innerText.trim()
                };
            }
            """
        )

        description = self._clean_text(detail.get("description", ""))
        return {
            "title": self._clean_text(detail.get("title", "")),
            "location": self._extract_location(self._clean_text(detail.get("text", ""))),
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
    def _clean_text(value: str | None) -> str:
        return " ".join((value or "").split())

    @staticmethod
    def _looks_like_job_url(url: str, title: str) -> bool:
        lower_url = url.lower()
        lower_title = title.lower()

        if not title or len(title) < 4:
            return False
        if not any(domain in lower_url for domain in MERCEDES_BENZ_JOB_DOMAINS):
            return False
        if any(skip in lower_url for skip in ("login", "linkedin", "instagram", "youtube", "privacy", "terms")):
            return False
        if lower_title in {"search", "job search", "jobs", "careers", "back", "next", "previous", "apply now"}:
            return False

        return any(marker in lower_url for marker in ("job", "career", "position", "vacancy", "requisition"))

    @staticmethod
    def _extract_location(text: str) -> str:
        labels = ("Location", "Standort", "City", "Ort", "Country/Region", "Office")
        lower_text = text.lower()
        for label in labels:
            marker = f"{label}:"
            if marker.lower() in lower_text:
                start = lower_text.find(marker.lower()) + len(marker)
                return text[start:].split("|", 1)[0].split("\n", 1)[0].strip()

        location_tokens = (
            "Munich",
            "Muenchen",
            "Berlin",
            "Hamburg",
            "Frankfurt",
            "Stuttgart",
            "Walldorf",
            "Germany",
            "Deutschland",
        )
        for token in location_tokens:
            match = re.search(token, text, re.IGNORECASE)
            if match:
                return text[match.start():].split("|", 1)[0].split("\n", 1)[0].split(",", 1)[0].strip()

        return ""

    @staticmethod
    def _extract_date_posted(text: str) -> str | None:
        labels = ("Date Posted:", "Posted:", "Publication Date:", "Published:", "Posting Date:")
        lower_text = text.lower()
        for label in labels:
            marker = label.lower()
            if marker not in lower_text:
                continue
            start = lower_text.find(marker) + len(marker)
            value = text[start:].strip().split(" ", 1)[0]
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
    collector = MercedesBenzCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.company} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
