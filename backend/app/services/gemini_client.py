"""Helpers for constructing google-genai clients with optional proxy base URL.

Render's egress IP is on Google's geo-restriction list even for paid Gemini
keys, so all calls go through a Cloudflare Worker proxy when
``GEMINI_API_BASE`` is set. The Worker forwards requests to
``generativelanguage.googleapis.com`` from a CF edge POP that Google does not
block.
"""

from urllib.parse import urlparse, urlunparse

from google import genai
from google.genai import types as genai_types

from app.config import get_settings


def _split_proxy_base(url: str) -> tuple[str, str]:
    """Split a proxy URL like ``https://worker.dev/<secret>`` into the origin
    (``https://worker.dev``) and the API-version path the SDK should use
    (``<secret>/v1beta``).

    The google-genai SDK builds request URLs as
    ``{base_url}/{api_version}/{resource}`` and discards any path component
    on ``base_url`` itself. So to embed the worker's path-prefix secret we
    have to put it into ``api_version``, not into the base URL path.
    """
    parsed = urlparse(url)
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    secret = parsed.path.strip("/")
    api_version = f"{secret}/v1beta" if secret else "v1beta"
    return origin, api_version


def make_genai_client() -> genai.Client:
    """Build a google-genai client, routed through GEMINI_API_BASE if set."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    if settings.gemini_api_base:
        # The Cloudflare Worker proxy authenticates via a path-prefix secret
        # baked into GEMINI_API_BASE (e.g. https://worker.dev/<secret>).
        # google-genai's HttpOptions(headers=...) doesn't actually forward
        # custom headers, and base_url's path is dropped during URL
        # construction — so we redirect the secret into api_version, which
        # the SDK does honour as a path segment.
        base_url, api_version = _split_proxy_base(settings.gemini_api_base)
        return genai.Client(
            api_key=settings.gemini_api_key,
            http_options=genai_types.HttpOptions(
                base_url=base_url,
                api_version=api_version,
            ),
        )
    return genai.Client(api_key=settings.gemini_api_key)
