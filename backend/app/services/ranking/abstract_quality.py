"""Heuristic guard for malformed or low-signal abstracts."""

import re

# Signals that the text is author biographies rather than an abstract.
# These patterns tend to appear only in bios and rarely in real abstracts.
_BIO_PATTERNS = [
    re.compile(r"\breceived (his|her|their|the) (Ph\.?D\.?|doctorate|degree)\b", re.IGNORECASE),
    re.compile(r"\bis (currently )?a (postdoctoral|post-doctoral|post doctoral|research fellow|professor|distinguished professor|associate professor|assistant professor|senior lecturer|lecturer|scientist|engineer)\b", re.IGNORECASE),
    re.compile(r"\bis (currently )?working (as|at)\b", re.IGNORECASE),
    re.compile(r"\bwas elected\b", re.IGNORECASE),
    re.compile(r"\bhis (main )?research interests?\b", re.IGNORECASE),
    re.compile(r"\bher (main )?research interests?\b", re.IGNORECASE),
]

# Minimum length for a plausible abstract, in characters.
MIN_ABSTRACT_CHARS = 150

# Methods-paper sanity signals. Real abstracts usually contain at least one of these.
_ABSTRACT_VERB_PATTERNS = re.compile(
    r"\b(we propose|we present|we develop|we show|we study|we investigate|"
    r"this paper|this work|this article|this study|"
    r"results show|results indicate|we demonstrate|we introduce|"
    r"the proposed|our approach|our method|our results|"
    r"in this|to address|motivated by)\b",
    re.IGNORECASE,
)


def abstract_quality(abstract: str | None) -> tuple[str, str | None]:
    """Return (quality_label, reason).

    quality_label is one of:
      "ok"           - looks like a real abstract
      "missing"      - no abstract at all
      "too_short"    - abstract shorter than MIN_ABSTRACT_CHARS
      "author_bios"  - abstract field contains author biographies, not methods
      "no_methods_verbs" - abstract is long enough but lacks any abstract-style verbs
    """
    if not abstract or not abstract.strip():
        return ("missing", None)
    text = abstract.strip()
    if len(text) < MIN_ABSTRACT_CHARS:
        return ("too_short", f"{len(text)} chars")

    # Count bio-pattern matches; multiple matches strongly suggest author bios
    bio_matches = sum(1 for p in _BIO_PATTERNS if p.search(text))
    if bio_matches >= 2:
        return ("author_bios", f"{bio_matches} bio patterns matched")

    # Abstract-verb signal is weaker but catches TOC entries and the like
    if not _ABSTRACT_VERB_PATTERNS.search(text):
        # Only flag if also somewhat short-ish (>150 but <500)
        # A long abstract without these verbs is possible but rare
        if len(text) < 500:
            return ("no_methods_verbs", None)

    return ("ok", None)
