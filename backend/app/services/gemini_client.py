"""Helpers for constructing google-genai clients with optional proxy base URL.

Render's egress IP is on Google's geo-restriction list even for paid Gemini
keys, so all calls go through a Cloudflare Worker proxy when
``GEMINI_API_BASE`` is set. The Worker forwards requests to
``generativelanguage.googleapis.com`` from a CF edge POP that Google does not
block.
"""

from google import genai
from google.genai import types as genai_types

from app.config import get_settings


def make_genai_client() -> genai.Client:
    """Build a google-genai client, routed through GEMINI_API_BASE if set."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    if settings.gemini_api_base:
        # The proxy worker authenticates via a path-prefix secret embedded
        # directly in GEMINI_API_BASE (e.g. https://worker.dev/<secret>),
        # because the google-genai SDK does not reliably forward custom
        # headers from HttpOptions(headers=...).
        return genai.Client(
            api_key=settings.gemini_api_key,
            http_options=genai_types.HttpOptions(base_url=settings.gemini_api_base),
        )
    return genai.Client(api_key=settings.gemini_api_key)
