"""Title-only hard-reject filter. Runs after the k-NN gate, before the LLM."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _build_title_pattern(keywords: list[str]) -> re.Pattern | None:
    """Build a case-insensitive word-boundary pattern from keywords.

    Short keywords (<=3 chars) use strict word boundaries to avoid false matches
    (e.g. "PCR" shouldn't match "PCRB"). Longer keywords use looser matching
    to catch inflections ("crystallisation" catches "crystallising").
    """
    if not keywords:
        return None
    parts = []
    for kw in keywords:
        escaped = re.escape(kw.strip())
        if not escaped:
            continue
        if len(kw.strip()) <= 3:
            parts.append(rf"\b{escaped}\b")
        else:
            parts.append(rf"\b{escaped}")  # prefix-style: matches inflections

    if not parts:
        return None
    return re.compile("|".join(parts), re.IGNORECASE)


def paper_rejected_by_title(paper: dict[str, Any], keywords: list[str]) -> tuple[bool, str | None]:
    """Return (rejected, matched_keyword). Title-only — never inspects the abstract."""
    pattern = _build_title_pattern(keywords)
    if pattern is None:
        return (False, None)
    title = (paper.get("title") or "").strip()
    if not title:
        return (False, None)
    m = pattern.search(title)
    if m:
        return (True, m.group(0).lower())
    return (False, None)
