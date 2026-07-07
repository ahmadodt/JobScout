from __future__ import annotations

import logging
import time
from typing import Sequence

import requests

from collectors.base import DEFAULT_KEYWORDS, Job, contains_keyword, dedupe_by_url


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
RETRY_BACKOFF_SECONDS = 2.0


class HttpCollectorBase:
    """Base for collectors that fetch jobs over plain HTTP (JSON APIs or HTML).

    Subclasses set `name` and `company` and implement `fetch_jobs()`;
    `collect()` wraps it with keyword filtering and URL dedupe.
    """

    name = "http"
    company = ""

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
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def collect(self) -> list[Job]:
        jobs = self.fetch_jobs()
        if self.filter_keywords:
            jobs = [job for job in jobs if self._job_matches_keywords(job)]
        return dedupe_by_url(jobs)

    def fetch_jobs(self) -> list[Job]:
        raise NotImplementedError

    def _job_matches_keywords(self, job: Job) -> bool:
        combined = " ".join((job.title, job.location, job.description))
        return contains_keyword(combined, self.keywords)

    def _get_json(self, url: str, params: dict | None = None) -> dict | list:
        response = self._get_with_retry(url, params)
        return response.json()

    def _get_html(self, url: str, params: dict | None = None) -> str:
        response = self._get_with_retry(url, params)
        return response.text

    def _get_with_retry(self, url: str, params: dict | None = None) -> requests.Response:
        timeout = (10, max(self.timeout_ms / 1000, 10))
        last_error: Exception | None = None

        for attempt in (1, 2):
            try:
                response = self.session.get(url, params=params, timeout=timeout)
                if response.status_code in RETRYABLE_STATUS_CODES and attempt == 1:
                    self.logger.warning(
                        "GET %s returned %s, retrying", url, response.status_code
                    )
                    time.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                response.raise_for_status()
                return response
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt == 1:
                    self.logger.warning("GET %s failed (%s), retrying", url, exc)
                    time.sleep(RETRY_BACKOFF_SECONDS)

        raise last_error if last_error else RuntimeError(f"GET {url} failed")
