"""Fetch curriculum documents from Supabase Storage and cache extracted text.

The crew YAML files (notes_crew, quiz_crew, assignment_crew) reference docs
by filename. Those filenames live in the public ``curriculum`` bucket on
Supabase Storage; this module turns a filename into a public URL, downloads
it, extracts text, and caches the result for the lifetime of the process.

Cache is in-memory and per-process. Single-instance Railway is fine for now;
when we scale to multiple replicas, replace ``_CACHE`` with Redis behind the
same interface.
"""

from __future__ import annotations

import urllib.parse

from app.config import get_settings
from app.services.file_fetch import fetch_docx_text, fetch_pdf_text

BUCKET = "curriculum"

_CACHE: dict[str, str] = {}


def _public_url(filename: str) -> str:
    base = get_settings().supabase_url.rstrip("/")
    encoded = urllib.parse.quote(filename, safe="")
    return f"{base}/storage/v1/object/public/{BUCKET}/{encoded}"


async def get_document_text(filename: str) -> str:
    """Return extracted text for one curriculum document.

    Returns ``""`` for entries that aren't real files (URLs, Google Doc
    titles without an extension, missing uploads) so callers can pass any
    reading-material entry through without pre-filtering.
    """
    if not filename or filename.startswith("http"):
        return ""
    if filename in _CACHE:
        return _CACHE[filename]
    url = _public_url(filename)
    lower = filename.lower()
    try:
        if lower.endswith(".pdf"):
            text = await fetch_pdf_text(url)
        elif lower.endswith((".docx", ".doc")):
            text = await fetch_docx_text(url)
        else:
            text = ""
    except Exception:
        text = ""
    _CACHE[filename] = text
    return text


async def get_documents_text(filenames: list[str]) -> str:
    """Concatenate extracted text for multiple files into one prompt block."""
    parts: list[str] = []
    for f in filenames:
        text = await get_document_text(f)
        if text:
            parts.append(f"--- {f} ---\n{text}")
    return "\n\n".join(parts)
