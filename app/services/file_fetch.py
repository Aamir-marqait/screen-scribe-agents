"""Download a file by URL and extract text from it.

Mirrors the n8n flow used by the script analyzer and assignment evaluator:
HTTP Request (download bytes) -> Extract from File (PDF/DOCX -> text). The
URL is typically a Supabase Storage URL; from the backend's perspective
it's just an HTTP fetch.
"""

from __future__ import annotations

from io import BytesIO

import httpx
from docx import Document
from pypdf import PdfReader

DEFAULT_TIMEOUT = 60  # seconds; PDFs can be large


async def download_bytes(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts).strip()


def extract_docx_text(data: bytes) -> str:
    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()


async def fetch_pdf_text(url: str) -> str:
    data = await download_bytes(url)
    return extract_pdf_text(data)


async def fetch_docx_text(url: str) -> str:
    data = await download_bytes(url)
    return extract_docx_text(data)
