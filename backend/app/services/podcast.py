import asyncio
import logging
import os
import struct
import tempfile
from typing import Any

import anthropic
import edge_tts

from app.config import get_settings

logger = logging.getLogger(__name__)

SINGLE_VOICE = "en-AU-WilliamNeural"
DUAL_VOICE_ALEX = "en-US-AndrewNeural"
DUAL_VOICE_SAM = "en-GB-SoniaNeural"

# Silence between speaker turns (milliseconds worth of silent MP3 frames)
INTER_TURN_SILENCE_MS = 600

SINGLE_VOICE_PROMPT = """Write a 3-4 minute spoken summary of this research paper in a clear, engaging \
academic podcast style. The listener is a researcher in energy systems. Avoid \
jargon without explanation. Cover: what problem it solves, how they solved it, \
what they found, and why it matters. Do not include music cues or sound effects. \
Write only the spoken words.

PAPER: {title}
SUMMARY: {summary}"""

DUAL_VOICE_SYSTEM = """You are an expert science podcast scriptwriter. You write scripts for a research \
discussion podcast with two hosts: Alex and Sam.

Rules:
- Alex (male, American accent) is the curious interviewer. He sets context, asks sharp follow-up \
questions, plays devil's advocate, and connects findings to the bigger picture.
- Sam (female, British accent) is the domain expert who has read the paper in depth. She explains \
methodology, results, and implications clearly and enthusiastically.
- Write NATURAL conversational dialogue — use contractions, interruptions, reactions \
("Right, that's interesting", "Exactly", "Wait, so you're saying...").
- Each turn should be 2-4 sentences. Avoid monologues.
- Never use filler words, sound effects, music cues, or stage directions like [laughs] or [pause].
- Never use made-up words, placeholder names, or technical abbreviations without expanding them first.
- The conversation should flow: opening hook → context → methodology → key findings → implications → takeaway.
- Write ONLY the dialogue lines, nothing else. No intro text, no notes.
- Target 5-6 minutes of spoken content (roughly 800-1000 words total)."""

DUAL_VOICE_PROMPT = """Write a conversational podcast script between Alex and Sam discussing this research paper.

Format each line exactly as:
ALEX: <dialogue>
SAM: <dialogue>

PAPER TITLE: {title}

PAPER SUMMARY:
{summary}"""


async def generate_script(
    title: str,
    summary: str,
    voice_mode: str = "single",
    client: anthropic.AsyncAnthropic | None = None,
    custom_prompt: str | None = None,
) -> str:
    """Generate a podcast script using Claude Sonnet."""
    settings = get_settings()
    if client is None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    is_dual = voice_mode == "dual"

    if custom_prompt:
        # User-provided prompt — append paper info
        user_message = custom_prompt + f"\n\nPAPER TITLE: {title}\n\nPAPER SUMMARY:\n{summary}"
    else:
        prompt = DUAL_VOICE_PROMPT if is_dual else SINGLE_VOICE_PROMPT
        user_message = prompt.format(title=title, summary=summary)

    kwargs: dict[str, Any] = {
        "model": settings.claude_model_smart,
        "max_tokens": 4000 if is_dual else 2000,
        "messages": [{"role": "user", "content": user_message}],
    }
    if is_dual and not custom_prompt:
        kwargs["system"] = DUAL_VOICE_SYSTEM

    try:
        response = await client.messages.create(**kwargs)
        script = response.content[0].text.strip()
        logger.info(f"Generated {voice_mode} script for '{title[:50]}...' ({len(script)} chars)")
        return script
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error during podcast script generation: {e}")
        raise


async def generate_audio_single(script: str, output_path: str, voice_id: str | None = None) -> None:
    """Generate single-voice MP3 using Edge TTS."""
    voice = voice_id or SINGLE_VOICE
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save(output_path)
    logger.info(f"Generated single-voice audio: {output_path} (voice={voice})")


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


def _generate_silence_mp3(duration_ms: int = 600) -> bytes:
    """Generate a short silent MP3 frame sequence.

    Creates minimal valid MP3 frames (MPEG1, Layer3, 128kbps, 44100Hz, mono)
    filled with silence. Each frame is 417 bytes covering ~26ms.
    """
    # MPEG1 Layer3 128kbps 44100Hz mono frame header
    header = b'\xff\xfb\x90\x00'
    frame_size = 417  # bytes per frame at 128kbps/44100Hz
    padding = b'\x00' * (frame_size - len(header))
    silent_frame = header + padding

    frames_needed = max(1, duration_ms // 26)
    return silent_frame * frames_needed


async def generate_audio_dual(
    script: str,
    output_path: str,
    alex_voice_id: str | None = None,
    sam_voice_id: str | None = None,
) -> None:
    """Generate dual-voice MP3 by generating segments with silence between turns."""
    segments = _parse_dual_script(script)
    if not segments:
        await generate_audio_single(script, output_path)
        return

    voice_alex = alex_voice_id or DUAL_VOICE_ALEX
    voice_sam = sam_voice_id or DUAL_VOICE_SAM
    silence_bytes = _generate_silence_mp3(INTER_TURN_SILENCE_MS)
    segment_files: list[str] = []

    try:
        for speaker, text in segments:
            voice = voice_alex if speaker == "alex" else voice_sam
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(tmp_path)
            segment_files.append(tmp_path)

        # Concatenate MP3 files with silence gaps between speaker turns
        with open(output_path, 'wb') as outfile:
            prev_speaker = None
            for i, seg_path in enumerate(segment_files):
                curr_speaker = segments[i][0]
                # Add silence on speaker change
                if prev_speaker is not None and curr_speaker != prev_speaker:
                    outfile.write(silence_bytes)
                with open(seg_path, 'rb') as infile:
                    outfile.write(infile.read())
                prev_speaker = curr_speaker

        logger.info(f"Generated dual-voice audio: {output_path} ({len(segments)} segments)")
    finally:
        for f in segment_files:
            if os.path.exists(f):
                os.unlink(f)


def _get_mp3_duration(filepath: str) -> int:
    """Estimate MP3 duration from file size. ~16KB per second at 128kbps."""
    try:
        size = os.path.getsize(filepath)
        return max(1, size // 16000)
    except Exception:
        return 0


async def generate_podcast(
    title: str,
    summary: str,
    voice_mode: str = "single",
    output_path: str | None = None,
    custom_prompt: str | None = None,
    custom_voices: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """Generate a complete podcast (script + audio).

    Returns:
        Tuple of (script, audio_path, duration_seconds).
    """
    script = await generate_script(title, summary, voice_mode, custom_prompt=custom_prompt)

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
