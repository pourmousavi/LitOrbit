import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

MASTER_KEYWORDS = [
    # Energy storage
    "battery", "BESS", "energy storage", "lithium", "degradation",
    "state of charge", "SOC", "SOH",
    # Power systems
    "power system", "grid", "transmission", "distribution",
    "frequency", "voltage", "stability",
    # Markets
    "electricity market", "NEM", "FCAS", "ancillary services",
    "market clearing", "dispatch", "bidding",
    # Renewables
    "solar", "wind", "renewable", "photovoltaic", "PV",
    # Forecasting & AI
    "forecasting", "machine learning", "deep learning", "neural network",
    "prediction", "optimization", "reinforcement learning",
    # Transport
    "electric vehicle", "EV", "charging", "V2G",
    # Specific methods
    "MILP", "convex", "stochastic", "robust optimization",
    "model predictive control", "MPC",
]


def _build_pattern(keywords: list[str]) -> re.Pattern:
    """Build a compiled regex pattern that matches any keyword (case-insensitive)."""
    escaped = [re.escape(kw) for kw in keywords]
    # Use word boundaries for short keywords to avoid false matches
    parts = []
    for kw, escaped_kw in zip(keywords, escaped):
        if len(kw) <= 3:
            parts.append(rf"\b{escaped_kw}\b")
        else:
            parts.append(escaped_kw)
    return re.compile("|".join(parts), re.IGNORECASE)


def prefilter_papers(
    papers: list[dict[str, Any]],
    keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter papers by keyword match in title or abstract.

    A paper passes if ANY keyword appears in its title OR abstract.

    Args:
        papers: List of paper dicts with 'title' and 'abstract' keys.
        keywords: Custom keyword list. Uses MASTER_KEYWORDS if None.

    Returns:
        Filtered list of papers that match at least one keyword.
    """
    if keywords is None:
        keywords = MASTER_KEYWORDS

    pattern = _build_pattern(keywords)
    passed = []
    blocked = 0

    for paper in papers:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        text = f"{title} {abstract}"

        if pattern.search(text):
            passed.append(paper)
        else:
            blocked += 1

    logger.info(
        f"Prefilter: {len(passed)} passed, {blocked} blocked "
        f"(from {len(papers)} total, using {len(keywords)} keywords)"
    )
    return passed
