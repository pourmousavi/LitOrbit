import asyncio
import io
import json
import logging
import os
import tempfile
import uuid
from typing import Any

import anthropic
import edge_tts

from app.config import get_settings

logger = logging.getLogger(__name__)

SINGLE_VOICE = "en-AU-WilliamNeural"
DUAL_VOICE_ALEX = "en-GB-RyanNeural"
DUAL_VOICE_SAM = "en-AU-NatashaNeural"

SINGLE_VOICE_PROMPT = """Write a 3-4 minute spoken summary of this research paper in a clear, engaging \
academic podcast style. The listener is a researcher in energy systems. Avoid \
jargon without explanation. Cover: what problem it solves, how they solved it, \
what they found, and why it matters. Do not include music cues or sound effects. \
Write only the spoken words.

PAPER: {title}
SUMMARY: {summary}"""

DUAL_VOICE_PROMPT = """Write a 4-5 minute conversational podcast script between two hosts discussing \
this research paper. Host A (Alex) is analytical and asks probing questions. \
Host B (Sam) explains the paper clearly and enthusiastically. \
Cover: context, methodology, key findings, implications.

Format as:
ALEX: [dialogue]
SAM: [dialogue]
ALEX: [dialogue]
...

PAPER: {title}
SUMMARY: {summary}"""


async def generate_script(
    title: str,
    summary: str,
    voice_mode: str = "single",
    client: anthropic.AsyncAnthropic | None = None,
) -> str:
    """Generate a podcast script using Claude Sonnet."""
    settings = get_settings()
    if client is None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = SINGLE_VOICE_PROMPT if voice_mode == "single" else DUAL_VOICE_PROMPT
    user_message = prompt.format(title=title, summary=summary)

    try:
        response = await client.messages.create(
            model=settings.claude_model_smart,
            max_tokens=2000,
            messages=[{"role": "user", "content": user_message}],
        )
        script = response.content[0].text.strip()
        logger.info(f"Generated {voice_mode} script for '{title[:50]}...' ({len(script)} chars)")
        return script
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error during podcast script generation: {e}")
        raise


async def generate_audio_single(script: str, output_path: str) -> None:
    """Generate single-voice MP3 using Edge TTS."""
    communicate = edge_tts.Communicate(script, SINGLE_VOICE)
    await communicate.save(output_path)
    logger.info(f"Generated single-voice audio: {output_path}")


def _parse_dual_script(script: str) -> list[tuple[str, str]]:
    """Parse a dual-voice script into (speaker, text) pairs."""
    segments: list[tuple[str, str]] = []
    current_speaker = ""
    current_text = ""

    for line in script.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.upper().startswith("ALEX:"):
            if current_speaker and current_text:
                segments.append((current_speaker, current_text.strip()))
            current_speaker = "alex"
            current_text = line[5:].strip()
        elif line.upper().startswith("SAM:"):
            if current_speaker and current_text:
                segments.append((current_speaker, current_text.strip()))
            current_speaker = "sam"
            current_text = line[4:].strip()
        else:
            current_text += " " + line

    if current_speaker and current_text:
        segments.append((current_speaker, current_text.strip()))

    return segments


async def generate_audio_dual(script: str, output_path: str) -> None:
    """Generate dual-voice MP3 by generating segments and concatenating."""
    from pydub import AudioSegment

    segments = _parse_dual_script(script)
    if not segments:
        # Fallback to single voice if parsing fails
        await generate_audio_single(script, output_path)
        return

    combined = AudioSegment.empty()

    for speaker, text in segments:
        voice = DUAL_VOICE_ALEX if speaker == "alex" else DUAL_VOICE_SAM

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(tmp_path)
            segment = AudioSegment.from_mp3(tmp_path)
            combined += segment + AudioSegment.silent(duration=300)  # 300ms pause between speakers
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    combined.export(output_path, format="mp3")
    logger.info(f"Generated dual-voice audio: {output_path} ({len(segments)} segments)")


async def generate_podcast(
    title: str,
    summary: str,
    voice_mode: str = "single",
    output_path: str | None = None,
) -> tuple[str, str, int]:
    """Generate a complete podcast (script + audio).

    Returns:
        Tuple of (script, audio_path, duration_seconds).
    """
    script = await generate_script(title, summary, voice_mode)

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3")

    if voice_mode == "dual":
        await generate_audio_dual(script, output_path)
    else:
        await generate_audio_single(script, output_path)

    # Get duration
    duration_seconds = 0
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(output_path)
        duration_seconds = int(len(audio) / 1000)
    except Exception:
        # Estimate from file size (~16kB per second for MP3 at 128kbps)
        try:
            file_size = os.path.getsize(output_path)
            duration_seconds = max(1, file_size // 16000)
        except Exception:
            duration_seconds = len(script) // 15  # ~15 chars per second of speech

    return script, output_path, duration_seconds
