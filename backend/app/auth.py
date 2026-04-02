import logging
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Validate Supabase JWT and return user info.

    Returns a dict with 'id' (UUID string) and user metadata.
    """
    settings = get_settings()
    token = credentials.credentials

    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Validate token against Supabase Auth
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_anon_key,
            },
        )

    if resp.status_code != 200:
        logger.warning(f"Auth validation failed: {resp.status_code}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    user_data = resp.json()
    return {
        "id": user_data.get("id"),
        "email": user_data.get("email"),
        "role": user_data.get("user_metadata", {}).get("role", "researcher"),
    }


async def require_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Require the current user to be an admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
