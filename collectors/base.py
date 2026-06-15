from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Job:
    title: str
    company: str
    location: str
    source: str
    url: str
    description: str
    date_posted: str | None
    date_collected: str


class Collector(Protocol):
    name: str

    def collect(self) -> list[Job]:
        ...


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
