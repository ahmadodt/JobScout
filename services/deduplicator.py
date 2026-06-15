from __future__ import annotations

import re


def normalize_text(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def make_dedupe_key(company: str, title: str) -> str:
    return f"{normalize_text(company)}::{normalize_text(title)}"
