from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONNECTIONS_PATH = Path(__file__).resolve().parents[1] / "personal_connections.json"


@dataclass(frozen=True)
class PersonalConnection:
    name: str
    relationship: str = ""
    notes: str = ""


@dataclass(frozen=True)
class CompanyConnections:
    company: str
    aliases: tuple[str, ...]
    connections: tuple[PersonalConnection, ...]
    notes: str = ""


def normalize_company_name(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", company.casefold())


def load_personal_connections(
    path: Path = DEFAULT_CONNECTIONS_PATH,
) -> dict[str, CompanyConnections]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    index: dict[str, CompanyConnections] = {}
    for item in payload.get("companies", []):
        company = _string_value(item.get("company"))
        if not company:
            continue

        aliases = tuple(
            alias
            for alias in (_string_value(value) for value in item.get("aliases", []))
            if alias
        )
        connections = tuple(
            PersonalConnection(
                name=_string_value(connection.get("name")),
                relationship=_string_value(connection.get("relationship")),
                notes=_string_value(connection.get("notes")),
            )
            for connection in item.get("connections", [])
            if _string_value(connection.get("name"))
        )
        company_connections = CompanyConnections(
            company=company,
            aliases=aliases,
            connections=connections,
            notes=_string_value(item.get("notes")),
        )

        for name in (company, *aliases):
            index[normalize_company_name(name)] = company_connections

    return index


def find_company_connections(
    company: str,
    connections: dict[str, CompanyConnections],
) -> CompanyConnections | None:
    return connections.get(normalize_company_name(company))


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
