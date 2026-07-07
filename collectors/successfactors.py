from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence
from urllib.parse import urljoin

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import DEFAULT_KEYWORDS, Job, clean_text, utc_now_iso
from collectors.http_base import HttpCollectorBase


ROWS_PER_PAGE = 25
# SuccessFactors locations look like "Walldorf, DE, 69190".
GERMANY_LOCATION_MARKERS = (", de", "germany", "deutschland")


class SuccessFactorsCollector(HttpCollectorBase):
    """Shared collector for SAP SuccessFactors career sites.

    These sites render search results server-side: rows are `a.jobTitle-link`
    anchors with sibling `span.jobLocation` / `span.jobDate` inside a `<tr>`.
    Subclasses set `name`, `company`, `base_url`, and optional `search_params`.
    """

    base_url = ""
    search_params: dict[str, str] = {}
    location_markers: tuple[str, ...] = GERMANY_LOCATION_MARKERS
    max_detail_pages = 60

    def __init__(
        self,
        timeout_ms: int = 45000,
        filter_keywords: bool = True,
        keywords: Sequence[str] = DEFAULT_KEYWORDS,
        max_pages: int = 3,
    ):
        super().__init__(
            timeout_ms=timeout_ms,
            filter_keywords=filter_keywords,
            keywords=keywords,
            max_pages=max_pages,
        )

    def fetch_jobs(self) -> list[Job]:
        from bs4 import BeautifulSoup

        collected_at = utc_now_iso()
        rows: dict[str, dict] = {}

        for keyword in self.keywords:
            for page in range(self.max_pages):
                params = {
                    "q": keyword,
                    "startrow": page * ROWS_PER_PAGE,
                    **self.search_params,
                }
                html = self._get_html(urljoin(self.base_url, "/search/"), params=params)
                soup = BeautifulSoup(html, "html.parser")
                anchors = soup.select("a.jobTitle-link")
                if not anchors:
                    break

                new_rows = 0
                for anchor in anchors:
                    url = urljoin(self.base_url, anchor.get("href", ""))
                    if not url or url in rows:
                        continue
                    row = anchor.find_parent("tr")
                    location = self._row_text(row, "span.jobLocation")
                    if not self._matches_location(location):
                        continue
                    rows[url] = {
                        "title": clean_text(anchor.get_text(" ")),
                        "location": location,
                        "date_posted": self._parse_date(self._row_text(row, "span.jobDate")),
                    }
                    new_rows += 1

                if new_rows == 0 or len(anchors) < ROWS_PER_PAGE:
                    break

        jobs = []
        for url, row in list(rows.items())[: self.max_detail_pages]:
            description = self._fetch_description(url)
            jobs.append(
                Job(
                    title=row["title"],
                    company=self.company,
                    location=row["location"],
                    source=self.name,
                    url=url,
                    description=description,
                    date_posted=row["date_posted"],
                    date_collected=collected_at,
                )
            )
        return jobs

    def _fetch_description(self, url: str) -> str:
        from bs4 import BeautifulSoup

        try:
            html = self._get_html(url)
        except Exception:
            self.logger.warning("detail page failed: %s", url, exc_info=True)
            return ""

        soup = BeautifulSoup(html, "html.parser")
        content = (
            soup.select_one("span[itemprop='description']")
            or soup.select_one(".jobdescription")
            or soup.select_one(".job")
            or soup.body
        )
        return clean_text(content.get_text(" ")) if content else ""

    def _matches_location(self, location: str) -> bool:
        if not self.location_markers:
            return True
        lower_location = location.lower()
        return any(marker in lower_location for marker in self.location_markers)

    @staticmethod
    def _row_text(row, selector: str) -> str:
        if row is None:
            return ""
        node = row.select_one(selector)
        return clean_text(node.get_text(" ")) if node else ""

    @staticmethod
    def _parse_date(value: str) -> str | None:
        if not value:
            return None
        for date_format in ("%b %d, %Y", "%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, date_format).date().isoformat()
            except ValueError:
                continue
        return None
