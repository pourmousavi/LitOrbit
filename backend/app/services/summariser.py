import json
import logging
from typing import Any

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert academic research summariser for an energy systems research group. \
Generate a structured summary of this paper for researchers in power systems, \
battery storage, electricity markets, and renewable energy."""

USER_PROMPT_TEMPLATE = """Generate a structured summary of this paper:

TITLE: {title}
AUTHORS: {authors}
JOURNAL: {journal}
ABSTRACT: {abstract}
{full_text_section}
Format your response as JSON with these exact keys:
{{
  "research_gap": "What problem or gap does this paper address? (2-3 sentences)",
  "methodology": "What methods, models, or approaches were used? (2-3 sentences)",
  "key_findings": "What are the 3-5 most important results or conclusions?",
  "relevance_to_energy_group": "Why is this relevant to energy systems research? (1-2 sentences)",
  "suggested_action": "read_fully | skim | monitor",
  "categories": ["list", "of", "2-4", "topic", "categories"]
}}"""

REQUIRED_KEYS = {
    "research_gap",
    "methodology",
    "key_findings",
    "relevance_to_energy_group",
    "suggested_action",
    "categories",
}


async def generate_summary(
    paper: dict[str, Any],
    client: anthropic.AsyncAnthropic | None = None,
) -> dict[str, Any] | None:
    """Generate a structured AI summary for a paper.

    Args:
        paper: Dict with title, authors, journal, abstract, and optionally full_text.
        client: Reusable Anthropic client.

    Returns:
        Dict with summary fields and categories, or None on failure.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping summary generation")
        return None

    if client is None:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    full_text = paper.get("full_text", "")
    full_text_section = ""
    if full_text:
        # Truncate to ~8000 chars to stay within context limits
        truncated = full_text[:8000]
        full_text_section = f"\nFULL TEXT (excerpt):\n{truncated}\n"

    authors_str = ", ".join(paper.get("authors", [])) if paper.get("authors") else "Unknown"

    user_message = USER_PROMPT_TEMPLATE.format(
        title=paper.get("title", ""),
        authors=authors_str,
        journal=paper.get("journal", ""),
        abstract=paper.get("abstract", ""),
        full_text_section=full_text_section,
    )

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text.strip()
        # Handle potential markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)

        # Validate required keys
        missing = REQUIRED_KEYS - set(result.keys())
        if missing:
            logger.warning(f"Summary missing keys: {missing}")

        logger.info(f"Generated summary for '{paper.get('title', '')[:50]}...'")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse summary JSON: {e}")
        return None
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error during summarisation: {e}")
        return None
