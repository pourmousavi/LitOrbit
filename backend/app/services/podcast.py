import asyncio
import logging
import os
import tempfile
from typing import Any

import anthropic
import edge_tts

from app.config import get_settings

logger = logging.getLogger(__name__)

SINGLE_VOICE = "en-AU-WilliamNeural"
DUAL_VOICE_ALEX = "en-US-AndrewNeural"
DUAL_VOICE_SAM = "en-GB-SoniaNeural"

# Silence between speaker turns
SILENCE_PAUSE_TEXT = "..."  # Edge TTS renders ellipsis as a natural brief pause

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


async def _generate_silence_mp3(voice: str) -> str:
    """Generate a short silence MP3 using Edge TTS with a pause text.

    Returns the path to the temporary MP3 file.
    """
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    communicate = edge_tts.Communicate(SILENCE_PAUSE_TEXT, voice)
    await communicate.save(tmp_path)
    return tmp_path


async def generate_audio_dual(
    script: str,
    output_path: str,
    alex_voice_id: str | None = None,
    sam_voice_id: str | None = None,
) -> None:
    """Generate dual-voice MP3 by generating segments with pauses between turns."""
    segments = _parse_dual_script(script)
    if not segments:
        await generate_audio_single(script, output_path)
        return

    voice_alex = alex_voice_id or DUAL_VOICE_ALEX
    voice_sam = sam_voice_id or DUAL_VOICE_SAM
    segment_files: list[str] = []
    silence_file: str | None = None

    try:
        # Pre-generate a single silence segment (reused between turns)
        silence_file = await _generate_silence_mp3(voice_alex)

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
                    with open(silence_file, 'rb') as sf:
                        outfile.write(sf.read())
                with open(seg_path, 'rb') as infile:
                    outfile.write(infile.read())
                prev_speaker = curr_speaker

        logger.info(f"Generated dual-voice audio: {output_path} ({len(segments)} segments)")
    finally:
        for f in segment_files:
            if os.path.exists(f):
                os.unlink(f)
        if silence_file and os.path.exists(silence_file):
            os.unlink(silence_file)


def _get_mp3_duration(filepath: str) -> int:
    """Calculate MP3 duration by parsing frame headers."""
    BITRATES = {
        0x01: 32, 0x02: 40, 0x03: 48, 0x04: 56, 0x05: 64,
        0x06: 80, 0x07: 96, 0x08: 112, 0x09: 128, 0x0A: 160,
        0x0B: 192, 0x0C: 224, 0x0D: 256, 0x0E: 320,
    }
    SAMPLE_RATES = {0x00: 44100, 0x01: 48000, 0x02: 32000}

    try:
        total_samples = 0
        sample_rate = 44100
        with open(filepath, 'rb') as f:
            data = f.read()

        i = 0
        while i < len(data) - 4:
            # Find sync word (0xFFE0 mask for MPEG1 Layer3)
            if data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
                i += 1
                continue

            header = data[i + 1:i + 4]
            bitrate_idx = (header[1] >> 4) & 0x0F
            sr_idx = (header[1] >> 2) & 0x03
            padding = (header[1] >> 1) & 0x01

            bitrate = BITRATES.get(bitrate_idx)
            sr = SAMPLE_RATES.get(sr_idx)
            if not bitrate or not sr:
                i += 1
                continue

            sample_rate = sr
            frame_size = (144 * bitrate * 1000 // sr) + padding
            if frame_size < 1:
                i += 1
                continue

            total_samples += 1152  # samples per MPEG1 Layer3 frame
            i += frame_size

        return max(1, total_samples // sample_rate) if total_samples > 0 else 0
    except Exception:
        # Fallback: rough estimate from file size
        try:
            return max(1, os.path.getsize(filepath) // 16000)
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
