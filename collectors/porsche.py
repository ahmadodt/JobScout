from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from collectors.base import Job, clean_text, utc_now_iso
from collectors.http_base import HttpCollectorBase


# jobs.porsche.com is a BeeSite (Milch & Zucker) portal; the search page loads
# results from this JSON API. PublicationChannel 12 is the public web channel.
API_URL = "https://porsche-beesite-production-gjb.app.beesite.de/search/"
PUBLICATION_CHANNEL = "12"

# The API keyword search matches substrings, so short keywords explode inside
# German words ("rag" hits "Vertrag"/"Frage" - 581 of 587 postings). Map those
# to precise stand-in terms; the word-boundary filter in collect() still runs
# against the real keywords afterwards.
SEARCH_TERM_ALIASES = {
    "rag": ("retrieval", "generative"),
}
# A term matching this many postings is substring noise, not a real signal.
MAX_RESULTS_PER_TERM = 200

DESCRIPTOR_FIELDS = [
    "ID",
    "PositionTitle",
    "PositionURI",
    "PositionLocation.CityName",
    "PositionLocation.CountryName",
    "PublicationStartDate",
]


class PorscheCollector(HttpCollectorBase):
    name = "porsche"
    company = "Porsche"

    def fetch_jobs(self) -> list[Job]:
        collected_at = utc_now_iso()
        jobs: list[Job] = []
        seen_ids: set[str] = set()

        for term in self._search_terms():
            for descriptor in self._search(term):
                job_id = str(descriptor.get("ID", ""))
                url = descriptor.get("PositionURI", "")
                if not job_id or not url or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                jobs.append(
                    Job(
                        title=clean_text(descriptor.get("PositionTitle", "")),
                        company=self.company,
                        location=self._format_location(descriptor),
                        source=self.name,
                        url=url,
                        description=self._fetch_description(url),
                        date_posted=descriptor.get("PublicationStartDate"),
                        date_collected=collected_at,
                    )
                )

        return jobs

    def _search_terms(self) -> list[str]:
        terms: list[str] = []
        for keyword in self.keywords:
            for term in SEARCH_TERM_ALIASES.get(keyword, (keyword,)):
                if term not in terms:
                    terms.append(term)
        return terms

    def _search(self, term: str) -> list[dict]:
        payload = {
            "LanguageCode": "EN",
            "SearchParameters": {
                "FirstItem": 1,
                "CountItem": MAX_RESULTS_PER_TERM,
                "Sort": [{"Criterion": "PublicationStartDate", "Direction": "DESC"}],
                "MatchedObjectDescriptor": DESCRIPTOR_FIELDS,
            },
            "SearchCriteria": [
                {
                    "CriterionName": "PositionFormattedDescription.Content",
                    "CriterionValue": [term],
                },
                {
                    "CriterionName": "PublicationChannel.Code",
                    "CriterionValue": [PUBLICATION_CHANNEL],
                },
            ],
        }
        body = self._get_json(API_URL, params={"data": json.dumps(payload)})
        result = body.get("SearchResult", {})

        total = result.get("SearchResultCountAll", 0)
        if total > MAX_RESULTS_PER_TERM:
            self.logger.warning(
                "search term %r matched %s Porsche postings - substring noise, skipping",
                term,
                total,
            )
            return []

        items = result.get("SearchResultItems") or []
        return [item.get("MatchedObjectDescriptor", {}) for item in items]

    def _fetch_description(self, url: str) -> str:
        try:
            html = self._get_html(url)
        except Exception:
            self.logger.warning("detail page failed: %s", url, exc_info=True)
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return clean_text(soup.get_text(" ", strip=True))

    @staticmethod
    def _format_location(descriptor: dict) -> str:
        locations = descriptor.get("PositionLocation") or []
        if not locations:
            return ""
        first = locations[0]
        parts = [first.get("CityName", ""), first.get("CountryName", "")]
        return clean_text(", ".join(part for part in parts if part))


if __name__ == "__main__":
    collector = PorscheCollector(filter_keywords=False)
    found_jobs = collector.collect()
    for found_job in found_jobs:
        print(f"{found_job.title} | {found_job.location} | {found_job.url}")
    print(f"Total: {len(found_jobs)}")
