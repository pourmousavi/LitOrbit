"""Supabase Storage helper for podcast audio files."""

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

BUCKET_NAME = "podcasts"


async def ensure_bucket_exists() -> None:
    """Create the podcasts bucket if it doesn't exist."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check if bucket exists
        resp = await client.get(
            f"{settings.supabase_url}/storage/v1/bucket/{BUCKET_NAME}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
            },
        )
        if resp.status_code == 200:
            return

        # Create bucket (public so audio can be streamed)
        resp = await client.post(
            f"{settings.supabase_url}/storage/v1/bucket",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
                "Content-Type": "application/json",
            },
            json={
                "id": BUCKET_NAME,
                "name": BUCKET_NAME,
                "public": True,
            },
        )
        if resp.status_code in (200, 201):
            logger.info(f"Created storage bucket '{BUCKET_NAME}'")
        else:
            logger.warning(f"Failed to create bucket: {resp.status_code} {resp.text}")


async def upload_audio(file_path: str, storage_key: str) -> Optional[str]:
    """Upload an MP3 file to Supabase Storage.

    Args:
        file_path: Local path to the MP3 file.
        storage_key: The key/path in the bucket (e.g., "abc123.mp3").

    Returns:
        Public URL of the uploaded file, or None on failure.
    """
    settings = get_settings()

    await ensure_bucket_exists()

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/storage/v1/object/{BUCKET_NAME}/{storage_key}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
                "Content-Type": "audio/mpeg",
            },
            content=file_bytes,
        )

    if resp.status_code in (200, 201):
        public_url = f"{settings.supabase_url}/storage/v1/object/public/{BUCKET_NAME}/{storage_key}"
        logger.info(f"Uploaded audio to storage: {storage_key}")
        return public_url
    else:
        logger.error(f"Failed to upload audio: {resp.status_code} {resp.text}")
        return None


async def delete_audio(storage_key: str) -> bool:
    """Delete an audio file from Supabase Storage."""
    settings = get_settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(
            f"{settings.supabase_url}/storage/v1/object/{BUCKET_NAME}/{storage_key}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
            },
        )

    return resp.status_code in (200, 204)
