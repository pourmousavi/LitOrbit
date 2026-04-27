"""Cloudflare Worker fetch proxy for news sources blocked by their WAF.

Used opt-in via NewsSource.use_proxy. The Worker
(scripts/news-fetch-proxy-worker.js) authenticates via a path-prefix
secret already embedded in NEWS_FETCH_PROXY_BASE, validates the target
hostname against an allowlist, and returns the upstream response body
verbatim with the upstream's status code and content-type.
"""

import logging
from urllib.parse import quote

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class ProxyNotConfiguredError(RuntimeError):
    """Raised when a source has use_proxy=true but the env var is missing."""


async def proxy_get(url: str, *, timeout: float = 30.0) -> httpx.Response:
    """Fetch ``url`` through the news-fetch CF Worker.

    Returns the underlying ``httpx.Response`` so callers can use ``.text``,
    ``.headers``, ``.status_code`` exactly as with a direct fetch.
    """
    base = get_settings().news_fetch_proxy_base
    if not base:
        raise ProxyNotConfiguredError(
            "NEWS_FETCH_PROXY_BASE is not set; cannot proxy this source"
        )

    proxied_url = f"{base.rstrip('/')}?url={quote(url, safe='')}"
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        return await client.get(proxied_url)
