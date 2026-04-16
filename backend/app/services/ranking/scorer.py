import asyncio
import json
import logging
import time
from typing import Any

from google import genai

from app.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_SCORING_PROMPT = """You are a research relevance scoring assistant. \
You will be given a paper's title, abstract, and keywords, along with a researcher's interest profile. \
Score the paper's relevance to this specific researcher on a scale of 0.0 to 10.0. \
Consider how well the paper's topic, methods, and findings align with the researcher's stated interests.

Return ONLY valid JSON in this exact format:
{"score": 7.5, "reasoning": "Brief explanation (under 30 words)."}

IMPORTANT: Keep the reasoning field under 30 words. Be concise."""

# Gemini free tier: 10 RPM, 250 RPD.
# We use a token-bucket rate limiter to stay under 9 RPM.
_RPM_LIMIT = 9
_INTERVAL = 60.0 / _RPM_LIMIT  # ~6.67 seconds between requests
_MAX_RETRIES = 3


class _RateLimiter:
    """Simple async rate limiter using a token-bucket approach."""

    def __init__(self, rpm: int = _RPM_LIMIT):
        self._interval = 60.0 / rpm
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


# Module-level rate limiter shared across all scoring calls
_rate_limiter = _RateLimiter()


async def score_paper_for_user(
    paper: dict[str, Any],
    user: dict[str, Any],
    client: genai.Client | None = None,
    custom_prompt: str | None = None,
) -> dict[str, Any]:
    """Score a single paper's relevance to a single user using Gemini Flash.

    Args:
        paper: Dict with 'title' and 'abstract'.
        user: Dict with 'full_name', 'interest_keywords', 'interest_categories'.
        client: Reusable Google GenAI client (created if not provided).

    Returns:
        Dict with 'score' (float) and 'reasoning' (str).
    """
    settings = get_settings()
    if client is None:
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY not set, returning default score")
            return {"score": 5.0, "reasoning": "API key not configured"}
        from app.services.gemini_client import make_genai_client
        client = make_genai_client()

    paper_keywords = ', '.join(paper.get('keywords', [])) if paper.get('keywords') else 'None provided'

    system_prompt = custom_prompt or DEFAULT_SCORING_PROMPT
    # Ensure the JSON format instruction is always present
    if '{"score"' not in system_prompt:
        system_prompt += '\n\nReturn ONLY valid JSON: {"score": 7.5, "reasoning": "..."}'

    # Render rating-derived category weights as a "learned preferences" line.
    # Positive weights = user has rated papers in this category highly;
    # negative weights = user has down-rated them. Only show non-trivial signal.
    learned_line = ""
    cw = user.get("category_weights") or {}
    if isinstance(cw, dict) and cw:
        significant = [(c, w) for c, w in cw.items() if isinstance(w, (int, float)) and abs(w) >= 0.2]
        significant.sort(key=lambda x: x[1], reverse=True)
        if significant:
            rendered = ", ".join(f"{c} ({w:+.1f})" for c, w in significant[:10])
            learned_line = f"\nLearned preferences from past ratings (positive=liked, negative=disliked): {rendered}"

    user_message = f"""PAPER TITLE: {paper.get('title', '')}
ABSTRACT: {paper.get('abstract', '')}
PAPER KEYWORDS: {paper_keywords}

RESEARCHER PROFILE:
Name: {user.get('full_name', '')}
Keywords of interest: {', '.join(user.get('interest_keywords', []))}
Research focus areas: {', '.join(user.get('interest_categories', []))}{learned_line}"""

    # Append semantic similarity if available (from embedding pre-filter)
    if paper.get("cosine_similarity") is not None:
        user_message += f"\nSEMANTIC SIMILARITY: {paper['cosine_similarity']}/1.0 (cosine similarity to researcher's reference papers)"

    for attempt in range(1, _MAX_RETRIES + 1):
        await _rate_limiter.acquire()
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.gemini_model_fast,
                    contents=user_message,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=1024,
                        response_mime_type="application/json",
                        response_schema={
                            "type": "object",
                            "properties": {
                                "score": {"type": "number"},
                                "reasoning": {"type": "string"},
                            },
                            "required": ["score", "reasoning"],
                        },
                    ),
                ),
                timeout=60,
            )

            raw_text = response.text
            if not raw_text:
                # Safety filter or empty completion. Surface the finish reason.
                finish_reason = None
                try:
                    finish_reason = response.candidates[0].finish_reason  # type: ignore[attr-defined]
                except Exception:
                    pass
                logger.error(
                    f"Scorer got empty response (finish_reason={finish_reason}) "
                    f"for paper '{paper.get('title', '')[:60]}'"
                )
                return {"score": 5.0, "reasoning": f"Empty AI response ({finish_reason})"}

            text = raw_text.strip()
            # Strip markdown code blocks if present
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(text)

            score = float(result.get("score", 5.0))
            score = max(0.0, min(10.0, score))
            reasoning = result.get("reasoning", "")

            logger.info(f"Scored '{paper.get('title', '')[:50]}...' for {user.get('full_name', '')}: {score}")
            return {"score": score, "reasoning": reasoning}

        except TimeoutError:
            logger.warning(f"Gemini scoring timed out for '{paper.get('title', '')[:60]}' (attempt {attempt}/{_MAX_RETRIES})")
            if attempt == _MAX_RETRIES:
                return {"score": 5.0, "reasoning": "Scoring timed out"}
            continue
        except json.JSONDecodeError as e:
            # Most common cause: response truncated by max_output_tokens.
            # Log the offending payload so we can diagnose, and retry once
            # before giving up.
            logger.error(
                f"Failed to parse scorer response as JSON for "
                f"'{paper.get('title', '')[:60]}': {e}. Raw text: {text!r}"
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(2)
                continue
            return {"score": 5.0, "reasoning": "Failed to parse AI response"}
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
                wait_time = 30 * attempt
                logger.warning(f"Rate limited (attempt {attempt}/{_MAX_RETRIES}), waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                if attempt == _MAX_RETRIES:
                    logger.error(f"Rate limit exceeded after {_MAX_RETRIES} retries")
                    return {"score": 5.0, "reasoning": "Rate limit exceeded"}
            else:
                logger.error(f"Gemini API error during scoring: {e}")
                return {"score": 5.0, "reasoning": "API error during scoring"}

    return {"score": 5.0, "reasoning": "Scoring failed after retries"}


async def score_paper_for_all_users(
    paper: dict[str, Any],
    users: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score a single paper for all users, rate-limited to stay within free tier.

    Returns:
        List of dicts with 'user_id', 'score', 'reasoning'.
    """
    from app.services.gemini_client import make_genai_client
    client = make_genai_client()

    # Run all tasks concurrently — the rate limiter serialises API calls
    tasks = [
        score_paper_for_user(paper, user, client, user.get("scoring_prompt"))
        for user in users
    ]
    results = await asyncio.gather(*tasks)

    scored = []
    for user, result in zip(users, results):
        scored.append({
            "user_id": user["id"],
            "score": result["score"],
            "reasoning": result["reasoning"],
        })
    return scored
