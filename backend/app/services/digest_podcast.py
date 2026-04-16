"""Digest podcast generation — produces a single podcast covering multiple papers."""

import asyncio
import logging
from typing import Any

import anthropic

from app.config import get_settings
from app.services.podcast import (
    generate_audio_single,
    generate_audio_dual,
    _get_mp3_duration,
)

logger = logging.getLogger(__name__)

DIGEST_SINGLE_PROMPT = """\
You are recording a research digest podcast episode. Summarise the following \
{count} papers in a clear, engaging academic podcast style. The listener is a \
researcher. For each paper, briefly cover what problem it addresses, the approach, \
and the key takeaway. Transition smoothly between papers. Keep the total length \
around {minutes} minutes of spoken content. Do not include music cues, sound \
effects, or section headings — write only the spoken words.

PAPERS:
{papers_block}"""

DIGEST_DUAL_SYSTEM = """\
You are an expert science podcast scriptwriter. You write scripts for a research \
digest podcast with two hosts: Alex and Sam.

Rules:
- Alex (male) is the curious interviewer. He introduces each paper, asks sharp \
follow-up questions, and connects findings across papers.
- Sam (female) is the domain expert who has read all the papers. She explains \
methodology, results, and implications clearly and enthusiastically.
- Write NATURAL conversational dialogue — use contractions, reactions \
("Right, that's interesting", "Exactly", "Wait, so you're saying...").
- Each turn should be 2-4 sentences. Avoid monologues.
- Never use filler words, sound effects, music cues, or stage directions.
- The conversation should flow: brief intro → paper 1 → paper 2 → ... → \
wrap-up with cross-cutting themes.
- Write ONLY the dialogue lines, nothing else. No intro text, no notes.
- Target {minutes} minutes of spoken content (roughly {words} words total)."""

DIGEST_DUAL_PROMPT = """\
Write a conversational podcast script between Alex and Sam discussing these \
{count} research papers in a digest format.

Format each line exactly as:
ALEX: <dialogue>
SAM: <dialogue>

PAPERS:
{papers_block}"""


def _build_papers_block(papers: list[dict[str, Any]]) -> str:
    """Format papers into a numbered block for the prompt."""
    lines = []
    for i, p in enumerate(papers, 1):
        parts = [f"[{i}] Title: {p['title']}"]
        if p.get("journal"):
            parts.append(f"    Journal: {p['journal']}")
        if p.get("score") is not None:
            parts.append(f"    Relevance: {p['score']:.1f}/10")
        if p.get("summary"):
            parts.append(f"    Summary: {p['summary']}")
        elif p.get("abstract"):
            parts.append(f"    Abstract: {p['abstract']}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def _estimate_minutes(count: int) -> int:
    """Rough target minutes based on paper count."""
    if count <= 3:
        return 5
    if count <= 6:
        return 8
    return 12


async def generate_digest_script(
    papers: list[dict[str, Any]],
    voice_mode: str = "dual",
    client: anthropic.AsyncAnthropic | None = None,
    custom_prompt: str | None = None,
) -> str:
    """Generate a podcast script covering multiple papers."""
    settings = get_settings()
    if client is None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    count = len(papers)
    papers_block = _build_papers_block(papers)
    minutes = _estimate_minutes(count)
    words = minutes * 150  # ~150 wpm for natural speech

    is_dual = voice_mode == "dual"

    if custom_prompt:
        user_message = custom_prompt + f"\n\nPAPERS:\n{papers_block}"
    elif is_dual:
        user_message = DIGEST_DUAL_PROMPT.format(count=count, papers_block=papers_block)
    else:
        user_message = DIGEST_SINGLE_PROMPT.format(
            count=count, papers_block=papers_block, minutes=minutes,
        )

    kwargs: dict[str, Any] = {
        "model": settings.claude_model_smart,
        "max_tokens": 6000,
        "messages": [{"role": "user", "content": user_message}],
    }
    if is_dual and not custom_prompt:
        kwargs["system"] = DIGEST_DUAL_SYSTEM.format(minutes=minutes, words=words)

    try:
        response = await asyncio.wait_for(
            client.messages.create(**kwargs),
            timeout=120,
        )
        script = response.content[0].text.strip()
        logger.info(
            f"Generated digest {voice_mode} script for {count} papers ({len(script)} chars)"
        )
        return script
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error during digest script generation: {e}")
        raise


async def generate_digest_podcast(
    papers: list[dict[str, Any]],
    voice_mode: str = "dual",
    output_path: str | None = None,
    custom_prompt: str | None = None,
    custom_voices: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """Generate a complete digest podcast (script + audio).

    Returns (script, audio_path, duration_seconds).
    """
    import tempfile

    script = await generate_digest_script(papers, voice_mode, custom_prompt=custom_prompt)

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3")

    voices = custom_voices or {}
    if voice_mode == "dual":
        await generate_audio_dual(
            script, output_path,
            alex_voice_id=voices.get("alex"),
            sam_voice_id=voices.get("sam"),
        )
    else:
        await generate_audio_single(script, output_path, voice_id=voices.get("single"))

    duration_seconds = _get_mp3_duration(output_path)
    return script, output_path, duration_seconds
