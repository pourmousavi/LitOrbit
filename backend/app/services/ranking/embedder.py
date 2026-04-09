import asyncio
import logging
import math
import time
from datetime import date
from typing import Any

from google import genai

from app.config import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMS = 3072

# Gemini Embedding free tier: 100 RPM, 1000 RPD, 30K TPM.
# Safety margins to avoid hitting hard limits.
_RPM_LIMIT = 90
_DAILY_LIMIT = 950
_MAX_RETRIES = 3


class EmbeddingQuotaExhausted(Exception):
    """Raised when the daily embedding quota is exhausted."""
    pass


class _EmbeddingRateLimiter:
    """Rate limiter with daily quota tracking for the Gemini Embedding API."""

    def __init__(self, rpm: int = _RPM_LIMIT, daily_limit: int = _DAILY_LIMIT):
        self._interval = 60.0 / rpm
        self._lock = asyncio.Lock()
        self._last_call = 0.0
        self._daily_limit = daily_limit
        self._daily_count = 0
        self._current_date: date | None = None

    def _reset_if_new_day(self):
        today = date.today()
        if self._current_date != today:
            self._daily_count = 0
            self._current_date = today

    async def acquire(self):
        async with self._lock:
            self._reset_if_new_day()
            if self._daily_count >= self._daily_limit:
                raise EmbeddingQuotaExhausted(
                    f"Gemini Embedding API daily limit reached ({self._daily_limit} requests). "
                    f"Quota resets at midnight. Papers without embeddings will use keyword "
                    f"fallback for scoring."
                )
            now = time.monotonic()
            wait = self._interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()
            self._daily_count += 1

    @property
    def daily_count(self) -> int:
        return self._daily_count

    @property
    def daily_remaining(self) -> int:
        self._reset_if_new_day()
        return max(0, self._daily_limit - self._daily_count)


_rate_limiter = _EmbeddingRateLimiter()

# Lazy singleton client
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        from app.services.gemini_client import make_genai_client
        _client = make_genai_client()
    return _client


def _normalize(vec: list[float]) -> list[float]:
    """L2-normalize a vector."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def prepare_paper_text(title: str, abstract: str | None) -> str:
    """Build the text to embed for a paper."""
    text = title
    if abstract:
        text = f"{title}. {abstract}"
    return " ".join(text.split())  # normalize whitespace


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Dot product of two normalized vectors (= cosine similarity)."""
    return sum(a * b for a, b in zip(vec_a, vec_b))


def compute_centroid(vectors: list[list[float]]) -> list[float]:
    """Compute the centroid (average) of vectors, then L2-normalize."""
    if not vectors:
        return []
    n = len(vectors)
    dims = len(vectors[0])
    centroid = [0.0] * dims
    for vec in vectors:
        for i, v in enumerate(vec):
            centroid[i] += v
    centroid = [c / n for c in centroid]
    return _normalize(centroid)


async def embed_text(text: str) -> list[float] | None:
    """Embed a single text using Gemini Embedding API.

    Returns normalized vector, or None on quota exhaustion.
    """
    result = await embed_texts([text])
    return result[0] if result else None


async def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """Embed multiple texts, respecting rate limits.

    Returns list of normalized vectors (or None for failed items).
    Stops early on quota exhaustion (remaining items get None).
    Raises EmbeddingAPIError for non-quota issues (bad key, network, etc).
    """
    client = _get_client()
    results: list[list[float] | None] = []
    quota_hit = False

    for text in texts:
        if quota_hit:
            results.append(None)
            continue
        embedding = await _embed_single(client, text)
        results.append(embedding)
        if embedding is None:
            quota_hit = True  # stop calling API, fill rest with None

    return results


class EmbeddingAPIError(Exception):
    """Non-quota API error — should stop retrying remaining papers."""
    pass


async def _embed_single(client: genai.Client, text: str) -> list[float] | None:
    """Embed a single text with rate limiting and retries.

    Returns vector on success, None on quota exhaustion.
    Raises EmbeddingAPIError for non-quota errors (bad key, network, etc).
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            await _rate_limiter.acquire()
        except EmbeddingQuotaExhausted:
            logger.warning("Embedding daily quota exhausted")
            return None

        try:
            response = await client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
            )
            vec = response.embeddings[0].values
            return _normalize(list(vec))

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
                wait_time = 30 * attempt
                logger.warning(f"Embedding rate limited (attempt {attempt}/{_MAX_RETRIES}), waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                if attempt == _MAX_RETRIES:
                    logger.error(f"Embedding rate limit exceeded after {_MAX_RETRIES} retries")
                    return None
            else:
                logger.error(f"Gemini Embedding API error: {e}")
                raise EmbeddingAPIError(str(e)) from e

    return None


def get_quota_status() -> dict[str, Any]:
    """Return current embedding quota status for admin visibility."""
    return {
        "daily_used": _rate_limiter.daily_count,
        "daily_remaining": _rate_limiter.daily_remaining,
        "daily_limit": _DAILY_LIMIT,
    }
