import logging
import re
from typing import Any

import fitz  # PyMuPDF
import httpx

logger = logging.getLogger(__name__)

MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF using PyMuPDF.

    Strips common headers/footers heuristically.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_text = []

    for page in doc:
        text = page.get_text()
        # Strip very short lines at top/bottom (likely headers/footers)
        lines = text.split("\n")
        if len(lines) > 4:
            # Remove first and last line if they look like headers/footers
            # (very short, often page numbers or journal names)
            filtered = []
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                # Skip very short lines at start/end that look like page numbers
                if (i < 2 or i > len(lines) - 3) and len(stripped) < 20 and re.match(r'^\d+$', stripped):
                    continue
                filtered.append(stripped)
            pages_text.append("\n".join(filtered))
        else:
            pages_text.append(text.strip())

    doc.close()
    full_text = "\n\n".join(pages_text)
    logger.info(f"Extracted {len(full_text)} chars from {len(pages_text)} pages")
    return full_text


def validate_pdf(file_bytes: bytes, filename: str) -> str | None:
    """Validate that the file is a PDF and within size limits.

    Returns error message or None if valid.
    """
    if len(file_bytes) > MAX_PDF_SIZE:
        return f"File too large ({len(file_bytes) / 1024 / 1024:.1f}MB). Maximum is 50MB."

    if not filename.lower().endswith(".pdf"):
        return "Only PDF files are accepted."

    # Check PDF magic bytes
    if not file_bytes[:5] == b"%PDF-":
        return "File does not appear to be a valid PDF."

    return None


async def fetch_pdf_from_unpaywall(doi: str, email: str = "litorbit@adelaide.edu.au") -> bytes | None:
    """Attempt to fetch an open-access PDF via Unpaywall.

    Args:
        doi: The DOI to look up.
        email: Contact email required by Unpaywall API.

    Returns:
        PDF bytes if found, None otherwise.
    """
    url = f"https://api.unpaywall.org/v2/{doi}"
    params = {"email": email}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.info(f"Unpaywall: no result for DOI {doi} (status {resp.status_code})")
                return None

            data = resp.json()
            best_oa = data.get("best_oa_location")
            if not best_oa:
                logger.info(f"Unpaywall: no OA location for DOI {doi}")
                return None

            pdf_url = best_oa.get("url_for_pdf")
            if not pdf_url:
                logger.info(f"Unpaywall: OA location has no PDF URL for DOI {doi}")
                return None

            # Download the PDF
            pdf_resp = await client.get(pdf_url)
            if pdf_resp.status_code == 200 and pdf_resp.content[:5] == b"%PDF-":
                logger.info(f"Unpaywall: downloaded PDF for DOI {doi} ({len(pdf_resp.content)} bytes)")
                return pdf_resp.content

            logger.info(f"Unpaywall: downloaded content is not a valid PDF for DOI {doi}")
            return None

        except httpx.RequestError as e:
            logger.error(f"Unpaywall request error for DOI {doi}: {e}")
            return None
