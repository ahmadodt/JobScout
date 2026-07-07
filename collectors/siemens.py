from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.base import Job, clean_text, utc_now_iso
from collectors.http_base import HttpCollectorBase


# Siemens runs an Avature career site; SearchJobs/{keyword} is server-rendered
# and job rows link to /JobDetail/{id}.
BASE_URL = "https://jobs.siemens.com"
SEARCH_URL = "https://jobs.siemens.com/en_US/externaljobs/SearchJobs/{keyword}"
MAX_DETAIL_PAGES = 40
COUNTRY_PATTERN = re.compile(
    r"\b(Germany|United States of America|United Kingdom|India|China|Thailand|"
    r"Singapore|Japan|South Korea|Korea|France|Spain|Italy|Austria|Switzerland|"
    r"Netherlands|Belgium|Portugal|Poland|Czechia|Hungary|Romania|Brazil|Mexico|"
    r"Canada|Australia|Turkiye|Turkey|Denmark|Sweden|Norway|Finland)\b"
)


class SiemensCollector(HttpCollectorBase):
    name = "siemens"
    company = "Siemens"

    def fetch_jobs(self) -> list[Job]:
        from bs4 import BeautifulSoup

        collected_at = utc_now_iso()
        titles_by_url: dict[str, str] = {}

        for keyword in self.keywords:
            html = self._get_html(SEARCH_URL.format(keyword=keyword))
            soup = BeautifulSoup(html, "html.parser")
            for anchor in soup.select("a[href]"):
                href = anchor.get("href", "")
                if "/JobDetail/" not in href:
                    continue
                url = urljoin(BASE_URL, href)
                title = clean_text(anchor.get_text(" "))
                # Each row links twice ("<title>" and "Learn more"); keep the longer text.
                if len(title) > len(titles_by_url.get(url, "")):
                    titles_by_url[url] = title

        jobs = []
        for url, title in list(titles_by_url.items())[:MAX_DETAIL_PAGES]:
            if not title or title.lower() == "learn more":
                continue
            detail = self._fetch_detail(url, title)
            jobs.append(
                Job(
                    title=title,
                    company=self.company,
                    location=detail["location"],
                    source=self.name,
                    url=url,
                    description=detail["description"],
                    date_posted=None,
                    date_collected=collected_at,
                )
            )
        return jobs

    def _fetch_detail(self, url: str, title: str = "") -> dict[str, str]:
        from bs4 import BeautifulSoup

        try:
            html = self._get_html(url)
        except Exception:
            self.logger.warning("detail page failed: %s", url, exc_info=True)
            return {"location": "", "description": ""}

        soup = BeautifulSoup(html, "html.parser")
        content = soup.select_one("main") or soup.body
        text = clean_text(content.get_text(" ")) if content else ""

        # The detail page renders "Location(s) <City> - <Region> - <Country>"
        # followed immediately by the job title repeating.
        location = ""
        match = re.search(r"Location\(?s?\)?\s*:?\s*(.{0,120})", text)
        if match:
            candidate = match.group(1)
            title_start = candidate.find(title[:15]) if title else -1
            if title_start > 0:
                candidate = candidate[:title_start]
            # "City - Region - Country ..." - cut after the first country name.
            country_match = COUNTRY_PATTERN.search(candidate)
            if country_match:
                candidate = candidate[: country_match.end()]
            location = clean_text(candidate)[:80].strip(" -")

        return {"location": location, "description": text}


if __name__ == "__main__":
    collector = SiemensCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.location} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
