"""Fetch curriculum documents from Supabase Storage and cache their text.

The crew YAML files (notes_crew, quiz_crew, assignment_crew) reference docs
by filename. Those filenames live in the public ``curriculum`` bucket on
Supabase Storage as pre-extracted ``.txt`` files; this module turns a
filename into a public URL, downloads it, and caches the result for the
lifetime of the process.

Cache is in-memory and per-process. Single-instance Railway is fine for now;
when we scale to multiple replicas, replace ``_CACHE`` with Redis behind the
same interface.
"""

from __future__ import annotations

import urllib.parse

from app.config import get_settings
from app.services.file_fetch import fetch_plain_text

BUCKET = "curriculum"

_CACHE: dict[str, str] = {}


def _public_url(filename: str) -> str:
    base = get_settings().supabase_url.rstrip("/")
    encoded = urllib.parse.quote(filename, safe="")
    return f"{base}/storage/v1/object/public/{BUCKET}/{encoded}"


async def get_document_text(filename: str) -> str:
    """Return text for one curriculum document.

    Curriculum docs are stored as ``.txt`` siblings of their original
    filenames. The YAMLs reference some entries with ``.pdf``/``.docx``
    extensions and others bare; we strip any known extension and append
    ``.txt`` so a single bucket layout serves all three crews.

    Returns ``""`` for entries that aren't real files (URLs, missing uploads).
    """
    if not filename or filename.startswith("http"):
        return ""
    if filename in _CACHE:
        return _CACHE[filename]

    base = filename
    lower = filename.lower()
    for ext in (".pdf", ".docx", ".doc"):
        if lower.endswith(ext):
            base = filename[: -len(ext)]
            break

    url = _public_url(base + ".txt")
    try:
        text = await fetch_plain_text(url)
    except Exception:
        text = ""

    _CACHE[filename] = text
    return text


async def get_documents_text(filenames: list[str]) -> str:
    """Concatenate text for multiple files into one prompt block."""
    parts: list[str] = []
    for f in filenames:
        text = await get_document_text(f)
        if text:
            parts.append(f"--- {f} ---\n{text}")
    return "\n\n".join(parts)
