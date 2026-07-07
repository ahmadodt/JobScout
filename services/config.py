from __future__ import annotations

import copy
from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.yaml"

DEFAULTS: dict = {
    "database": {"path": "jobscout.sqlite3"},
    "schedule": {"collection_time": "08:00", "scoring_time": "08:30"},
    "scoring": {"ai_enabled": False},
    "collection": {"lookback_days": 30, "keywords": ["rag", "llm", "agent"]},
    "cleanup": {"stale_days": 30},
    "collectors": {
        "greenhouse": {"enabled": False, "boards": []},
        "lever": {"enabled": False, "boards": []},
        "ashby": {"enabled": False, "boards": []},
    },
}


def load_config(path: Path = CONFIG_PATH) -> dict:
    config = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
    return _merge(copy.deepcopy(DEFAULTS), config)


def save_config(config: dict, path: Path = CONFIG_PATH) -> None:
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file, sort_keys=False, allow_unicode=True)


def resolve_db_path(config: dict) -> Path:
    return ROOT_DIR / config["database"]["path"]


def _merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge(base[key], value)
        else:
            base[key] = value
    return base
