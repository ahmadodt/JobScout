from __future__ import annotations

import inspect

from collectors.allianz import AllianzCollector
from collectors.amazon import AmazonCollector
from collectors.apple import AppleCollector
from collectors.base import Collector, DEFAULT_KEYWORDS
from collectors.bmw import BMWCollector
from collectors.google import GoogleCollector
from collectors.mercedes_benz import MercedesBenzCollector
from collectors.meta import MetaCollector
from collectors.microsoft_germany import MicrosoftGermanyCollector
from collectors.mock import MockCollector
from collectors.porsche import PorscheCollector
from collectors.sap import SAPCollector
from collectors.siemens import SiemensCollector
from collectors.volkswagen import VolkswagenCollector


AVAILABLE_COLLECTORS: dict[str, type] = {
    "mock": MockCollector,
    "bmw": BMWCollector,
    "porsche": PorscheCollector,
    "mercedes_benz": MercedesBenzCollector,
    "volkswagen": VolkswagenCollector,
    "siemens": SiemensCollector,
    "sap": SAPCollector,
    "allianz": AllianzCollector,
    "microsoft_germany": MicrosoftGermanyCollector,
    "google": GoogleCollector,
    "meta": MetaCollector,
    "apple": AppleCollector,
    "amazon": AmazonCollector,
}

# ATS platforms expanded from config `boards` lists rather than one class per company.
BOARD_COLLECTOR_NAMES = ("greenhouse", "lever", "ashby")


def _supported_kwargs(collector_class: type, kwargs: dict) -> dict:
    parameters = inspect.signature(collector_class.__init__).parameters
    return {key: value for key, value in kwargs.items() if key in parameters}


def _build_single(name: str, collector_class: type, config: dict, overrides: dict | None = None) -> Collector:
    collector_config = config.get("collectors", {}).get(name, {})
    global_keywords = config.get("collection", {}).get("keywords") or list(DEFAULT_KEYWORDS)

    kwargs = {
        "keywords": collector_config.get("keywords", global_keywords),
        "timeout_ms": collector_config.get("timeout_ms", 45000),
        "max_pages": collector_config.get("max_pages", 1),
    }
    if overrides:
        kwargs.update(overrides)
    return collector_class(**_supported_kwargs(collector_class, kwargs))


def _build_board_collectors(platform: str, config: dict) -> list[tuple[str, Collector]]:
    platform_config = config.get("collectors", {}).get(platform, {})
    boards = platform_config.get("boards") or []
    if not boards:
        return []

    if platform == "greenhouse":
        from collectors.greenhouse import GreenhouseCollector as board_class
    elif platform == "lever":
        from collectors.lever import LeverCollector as board_class
    elif platform == "ashby":
        from collectors.ashby import AshbyCollector as board_class
    else:
        return []

    global_keywords = config.get("collection", {}).get("keywords") or list(DEFAULT_KEYWORDS)
    collectors = []
    for board in boards:
        collector = board_class(
            slug=board["slug"],
            company=board.get("company", board["slug"].title()),
            keywords=board.get("keywords", global_keywords),
            locations=board.get("locations"),
            timeout_ms=platform_config.get("timeout_ms", 45000),
        )
        collectors.append((collector.name, collector))
    return collectors


def build_collectors(config: dict) -> list[tuple[str, Collector]]:
    """Instantiate all enabled collectors from config.

    Returns (name, collector) pairs; board platforms (greenhouse/lever/ashby)
    expand into one collector per configured board.
    """
    collectors_config = config.get("collectors", {})
    built: list[tuple[str, Collector]] = []

    for name, collector_class in AVAILABLE_COLLECTORS.items():
        if not collectors_config.get(name, {}).get("enabled", False):
            continue
        built.append((name, _build_single(name, collector_class, config)))

    for platform in BOARD_COLLECTOR_NAMES:
        if not collectors_config.get(platform, {}).get("enabled", False):
            continue
        built.extend(_build_board_collectors(platform, config))

    return built
