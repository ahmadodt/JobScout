from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from typing import Sequence
from urllib.parse import urljoin

from collectors.base import (
    DEFAULT_KEYWORDS,
    Job,
    clean_text,
    contains_keyword,
    dedupe_by_url,
    utc_now_iso,
)


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
RETRY_BACKOFF_SECONDS = 2.0


class PlaywrightCollectorBase:
    """Shared Playwright scraping template.

    Subclasses override the class constants (and optionally the hooks
    `paginate`, `accept_listing`, `looks_like_job_url`) instead of
    duplicating the whole scrape loop.
    """

    name = "browser"
    company = ""
    search_urls: tuple[str, ...] = ()
    # Alternative to search_urls: templates with a {keyword} placeholder,
    # expanded once per configured keyword.
    search_url_templates: tuple[str, ...] = ()
    job_url_domains: tuple[str, ...] = ()
    job_url_markers: tuple[str, ...] = (
        "job",
        "career",
        "position",
        "vacancy",
        "requisition",
    )
    skip_url_tokens: tuple[str, ...] = (
        "login",
        "linkedin",
        "instagram",
        "youtube",
        "privacy",
        "terms",
    )
    title_blocklist: frozenset[str] = frozenset(
        {"search", "job search", "jobs", "careers", "back", "next", "previous", "apply now"}
    )
    content_wait_selectors: tuple[str, ...] = (
        "a[href*='job']",
        "a[href*='career']",
        "[class*='job'] a[href]",
        "[class*='career'] a[href]",
        "[data-testid*='job'] a[href]",
    )
    detail_timeout_cap_ms = 15000

    def __init__(
        self,
        timeout_ms: int = 45000,
        filter_keywords: bool = True,
        keywords: Sequence[str] = DEFAULT_KEYWORDS,
        max_pages: int = 1,
    ):
        self.timeout_ms = timeout_ms
        self.filter_keywords = filter_keywords
        self.keywords = tuple(keywords)
        self.max_pages = max_pages
        self.logger = logging.getLogger(f"collectors.{self.name}")

    def collect(self) -> list[Job]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                f"{type(self).__name__} requires Playwright. Install it with "
                "`pip install playwright` and then run `playwright install chromium`."
            ) from exc

        collected_at = utc_now_iso()
        jobs: list[Job] = []
        seen_urls: set[str] = set()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=DEFAULT_USER_AGENT, locale="en-US"
            )
            page = context.new_page()
            detail_page = context.new_page()

            try:
                for search_url in self.build_search_urls():
                    try:
                        self._goto_with_retry(page, search_url, self.timeout_ms)
                        self._wait_for_job_content(page, PlaywrightTimeoutError)
                        self.after_search_load(page, PlaywrightTimeoutError)
                    except Exception:
                        self.logger.warning(
                            "failed to open search page %s", search_url, exc_info=True
                        )
                        continue

                    page_number = 1
                    while True:
                        listings = self._extract_listing_links(page, search_url)
                        new_listings = [
                            listing
                            for listing in listings
                            if listing["url"] and listing["url"] not in seen_urls
                        ]
                        self._collect_listing_batch(
                            new_listings, detail_page, collected_at, jobs, seen_urls
                        )

                        if self.should_stop_paginating(listings):
                            break
                        if page_number >= self.max_pages:
                            break
                        if not self.paginate(page, PlaywrightTimeoutError):
                            break
                        page_number += 1
            finally:
                browser.close()

        return dedupe_by_url(jobs)

    # ------------------------------------------------------------------
    # Hooks for subclasses

    def build_search_urls(self) -> list[str]:
        if self.search_url_templates:
            return [
                template.format(keyword=keyword)
                for template in self.search_url_templates
                for keyword in self.keywords
            ]
        return list(self.search_urls)

    def after_search_load(self, page, timeout_error) -> None:
        """Runs once per search page after it loads (e.g. bump page size)."""

    def paginate(self, page, timeout_error) -> bool:
        """Advance to the next page of results. Return False when done."""
        return False

    def should_stop_paginating(self, listings: list[dict[str, str | None]]) -> bool:
        """Early-stop hook (e.g. BMW stops once listings get too old)."""
        return False

    def accept_listing(self, listing: dict[str, str | None]) -> bool:
        """Per-listing filter before the detail page is fetched."""
        return True

    def looks_like_job_url(self, url: str, title: str) -> bool:
        lower_url = url.lower()
        lower_title = title.lower()

        if not title or len(title) < 4:
            return False
        if self.job_url_domains and not any(
            domain in lower_url for domain in self.job_url_domains
        ):
            return False
        if any(skip in lower_url for skip in self.skip_url_tokens):
            return False
        if lower_title in self.title_blocklist:
            return False

        return any(marker in lower_url for marker in self.job_url_markers)

    # ------------------------------------------------------------------
    # Template internals

    def _goto_with_retry(self, page, url: str, timeout_ms: int) -> None:
        for attempt in (1, 2):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                return
            except Exception as exc:
                if attempt == 2:
                    raise
                self.logger.warning("goto %s failed (%s), retrying", url, exc)
                time.sleep(RETRY_BACKOFF_SECONDS)

    def _collect_listing_batch(
        self,
        listings: list[dict[str, str | None]],
        detail_page,
        collected_at: str,
        jobs: list[Job],
        seen_urls: set[str],
    ) -> None:
        for listing in listings:
            url = listing["url"]
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            if not self.accept_listing(listing):
                continue

            detail = self._extract_detail_page(detail_page, url)
            if not detail:
                continue

            description = detail["description"]
            combined_text = " ".join(
                part or ""
                for part in (detail["title"], detail["location"], description)
            )
            if self.filter_keywords and not contains_keyword(
                combined_text, self.keywords
            ):
                continue

            jobs.append(
                Job(
                    title=detail["title"] or listing["title"] or "",
                    company=self.company,
                    location=detail["location"] or listing["location"] or "",
                    source=self.name,
                    url=url,
                    description=description,
                    date_posted=detail["date_posted"] or listing["date_posted"],
                    date_collected=collected_at,
                )
            )

    def _wait_for_job_content(self, page, timeout_error) -> None:
        for selector in self.content_wait_selectors:
            try:
                page.wait_for_selector(selector, timeout=self.timeout_ms)
                return
            except timeout_error:
                continue
        self.logger.warning(
            "%s: no job-content selector appeared on %s", self.name, page.url
        )

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
            title = clean_text(link.get("title", ""))
            listing_text = clean_text(link.get("text", ""))

            if not self.looks_like_job_url(url, title):
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
        detail_timeout_ms = min(self.timeout_ms, self.detail_timeout_cap_ms)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=detail_timeout_ms)
            page.wait_for_selector("body", timeout=detail_timeout_ms)
        except Exception:
            self.logger.warning("detail page failed: %s", url, exc_info=True)
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

        description = clean_text(detail.get("description", ""))
        return {
            "title": clean_text(detail.get("title", "")),
            "location": self._extract_location(clean_text(detail.get("text", ""))),
            "description": description,
            "date_posted": self._extract_date_posted(description),
        }

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
                return (
                    text[match.start():]
                    .split("|", 1)[0]
                    .split("\n", 1)[0]
                    .split(",", 1)[0]
                    .strip()
                )

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
    def _parse_date(value: str | None) -> date | None:
        if not value:
            return None

        for date_format in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue

        return None
