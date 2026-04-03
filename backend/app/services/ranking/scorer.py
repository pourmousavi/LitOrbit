import asyncio
import json
import logging
from typing import Any

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a research relevance scoring assistant for an academic research group \
specialising in battery energy storage systems, electricity markets, power system \
operation, renewable energy integration, and AI/ML methods for energy systems.

You will be given a paper's title and abstract, and a researcher's interest profile. \
Score the paper's relevance to this specific researcher on a scale of 0.0 to 10.0. \
Return ONLY valid JSON in this exact format:
{"score": 7.5, "reasoning": "One sentence explanation of why this score was given."}"""


async def score_paper_for_user(
    paper: dict[str, Any],
    user: dict[str, Any],
    client: anthropic.AsyncAnthropic | None = None,
) -> dict[str, Any]:
    """Score a single paper's relevance to a single user using Claude Haiku.

    Args:
        paper: Dict with 'title' and 'abstract'.
        user: Dict with 'full_name', 'interest_keywords', 'interest_categories'.
        client: Reusable Anthropic client (created if not provided).

    Returns:
        Dict with 'score' (float) and 'reasoning' (str).
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set, returning default score")
        return {"score": 5.0, "reasoning": "API key not configured"}

    if client is None:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    user_message = f"""PAPER TITLE: {paper.get('title', '')}
ABSTRACT: {paper.get('abstract', '')}

RESEARCHER PROFILE:
Name: {user.get('full_name', '')}
Keywords of interest: {', '.join(user.get('interest_keywords', []))}
Research focus areas: {', '.join(user.get('interest_categories', []))}"""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text.strip()
        result = json.loads(text)

        score = float(result.get("score", 5.0))
        score = max(0.0, min(10.0, score))
        reasoning = result.get("reasoning", "")

        logger.info(f"Scored '{paper.get('title', '')[:50]}...' for {user.get('full_name', '')}: {score}")
        return {"score": score, "reasoning": reasoning}

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse scorer response as JSON: {e}")
        return {"score": 5.0, "reasoning": "Failed to parse AI response"}
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error during scoring: {e}")
        return {"score": 5.0, "reasoning": "API error during scoring"}


async def score_paper_for_all_users(
    paper: dict[str, Any],
    users: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score a single paper for all users in parallel.

    Returns:
        List of dicts with 'user_id', 'score', 'reasoning'.
    """
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    tasks = [
        score_paper_for_user(paper, user, client)
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
