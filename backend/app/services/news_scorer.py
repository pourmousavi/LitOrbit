"""LLM scoring and summarisation for news items.

Uses the same Gemini model as paper scoring but with news-appropriate prompts.
Produces a 0-10 score and a structured summary.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_item import NewsItem
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

NEWS_SCORING_PROMPT = """You are a relevance scoring assistant for an energy industry researcher. \
You will be given a news article's title and content, along with a researcher's interest profile. \
Score the article's relevance to this researcher on a scale of 0.0 to 10.0. \
Consider: does this article inform their research? Does it cover industry developments \
(BESS, grid, renewables, markets, regulation) relevant to their work?

Return ONLY valid JSON in this exact format:
{"score": 7.5, "reasoning": "Brief explanation (under 30 words)."}

IMPORTANT: Keep the reasoning field under 30 words. Be concise."""

NEWS_SUMMARY_SYSTEM = """You are an expert industry news analyst for an energy systems research group. \
Generate a structured summary of this news article for researchers in power systems, \
battery storage, electricity markets, and renewable energy."""

NEWS_SUMMARY_USER = """Summarise this news article:

TITLE: {title}
SOURCE: {source}
CONTENT: {content}

Format your response as JSON with these exact keys:
{{
  "key_points": "What are the 2-3 most important facts or developments? (3-5 sentences)",
  "industry_impact": "What does this mean for the energy industry? (1-2 sentences)",
  "relevance": "Why is this relevant to energy systems researchers? (1 sentence)",
  "suggested_action": "read_fully | skim | monitor",
  "categories": ["list", "of", "2-6", "topic", "categories"]
}}"""


def _extract_json(text: str) -> str:
    """Robustly extract JSON from LLM responses that may include markdown fences."""
    text = text.strip()
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Find first { ... last } as fallback
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


async def score_news_for_user(
    item: NewsItem,
    user: dict[str, Any],
    source_name: str,
) -> dict[str, Any]:
    """Score a news item's relevance to a user using Gemini."""
    from app.services.gemini_client import make_genai_client
    from app.services.ranking.scorer import _rate_limiter
    from google import genai
    from app.config import get_settings

    settings = get_settings()
    client = make_genai_client()

    content = item.full_text or item.excerpt or ""
    if len(content) > 4000:
        content = content[:4000]

    learned_line = ""
    cw = user.get("category_weights") or {}
    if isinstance(cw, dict) and cw:
        significant = [(c, w) for c, w in cw.items() if isinstance(w, (int, float)) and abs(w) >= 0.2]
        significant.sort(key=lambda x: x[1], reverse=True)
        if significant:
            rendered = ", ".join(f"{c} ({w:+.1f})" for c, w in significant[:10])
            learned_line = f"\nLearned preferences from past ratings (positive=liked, negative=disliked): {rendered}"

    user_message = f"""NEWS TITLE: {item.title}
SOURCE: {source_name}
CONTENT: {content}

RESEARCHER PROFILE:
Name: {user.get('full_name', '')}
Keywords of interest: {', '.join(user.get('interest_keywords', []))}
Research focus areas: {', '.join(user.get('interest_categories', []))}{learned_line}"""

    await _rate_limiter.acquire()
    try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=settings.gemini_model_fast,
                contents=user_message,
                config=genai.types.GenerateContentConfig(
                    system_instruction=NEWS_SCORING_PROMPT,
                    max_output_tokens=512,
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
        text = response.text.strip()
        text = _extract_json(text)
        result = json.loads(text)
        score = max(0.0, min(10.0, float(result.get("score", 5.0))))
        return {"score": score, "reasoning": result.get("reasoning", ""), "error": False}
    except Exception as e:
        logger.warning("News scoring failed for '%s': %s", item.title[:50], e)
        return {"score": None, "reasoning": str(e), "error": True}


async def summarise_news(item: NewsItem, source_name: str) -> dict[str, Any] | None:
    """Generate a structured summary for a news item using Claude."""
    import anthropic
    from app.config import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping news summary")
        return None

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    content = item.full_text or item.excerpt or ""
    if len(content) > 6000:
        content = content[:6000]

    user_message = NEWS_SUMMARY_USER.format(
        title=item.title,
        source=source_name,
        content=content,
    )

    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model=settings.claude_model_smart,
                max_tokens=800,
                system=NEWS_SUMMARY_SYSTEM,
                messages=[{"role": "user", "content": user_message}],
            ),
            timeout=90,
        )
        text = response.content[0].text.strip()
        text = _extract_json(text)
        result = json.loads(text)
        logger.info("Generated news summary for '%s'", item.title[:50])
        return result
    except Exception as e:
        logger.warning("News summary failed for '%s': %s", item.title[:50], e)
        return None


async def score_and_summarise_news_item(
    db: AsyncSession,
    item: NewsItem,
    source_name: str,
) -> None:
    """Score and summarise a single news item, updating the DB row."""
    from sqlalchemy import select

    # Get first user for scoring (single-user system)
    user_result = await db.execute(select(UserProfile).limit(1))
    user_profile = user_result.scalar_one_or_none()
    if not user_profile:
        return

    user_dict = {
        "id": str(user_profile.id),
        "full_name": user_profile.full_name,
        "interest_keywords": user_profile.interest_keywords or [],
        "interest_categories": user_profile.interest_categories or [],
        "category_weights": user_profile.category_weights or {},
    }

    # Score
    score_result = await score_news_for_user(item, user_dict, source_name)
    if not score_result.get("error"):
        item.llm_score = score_result["score"]
        item.llm_score_reasoning = score_result["reasoning"]

    # Summarise (only if we have enough content)
    content = item.full_text or item.excerpt or ""
    if len(content) >= 100:
        summary = await summarise_news(item, source_name)
        if summary:
            item.summary = json.dumps(summary)
            item.summary_generated_at = datetime.now(timezone.utc)
            if summary.get("categories"):
                item.categories = summary["categories"][:6]

    await db.commit()
