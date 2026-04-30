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


async def _try_fetch(filename: str) -> str:
    """Try to download+extract a single concrete filename. Returns ``""`` on any failure."""
    url = _public_url(filename)
    lower = filename.lower()
    try:
        if lower.endswith(".pdf"):
            return await fetch_pdf_text(url)
        if lower.endswith((".docx", ".doc")):
            return await fetch_docx_text(url)
    except Exception:
        return ""
    return ""


async def get_document_text(filename: str) -> str:
    """Return extracted text for one curriculum document.

    Returns ``""`` for entries that aren't real files (URLs, missing uploads)
    so callers can pass any reading-material entry through without pre-filtering.

    notes_crew's reading_materials.yaml lists titles WITHOUT an extension
    (e.g. ``Short stories by Guy de Maupassant``), while quiz_crew uses
    ``.pdf``-suffixed names. To support both without mutating either YAML,
    when the name has no known extension we try ``.pdf`` then ``.docx``.
    """
    if not filename or filename.startswith("http"):
        return ""
    if filename in _CACHE:
        return _CACHE[filename]

    lower = filename.lower()
    if lower.endswith((".pdf", ".docx", ".doc")):
        text = await _try_fetch(filename)
    else:
        text = await _try_fetch(filename + ".pdf")
        if not text:
            text = await _try_fetch(filename + ".docx")

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
