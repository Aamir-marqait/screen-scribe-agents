"""One-shot: list the Supabase ``curriculum`` bucket and diff against
the 33 .txt files the crews expect. Reads creds from .env."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
BUCKET = "curriculum"


def expected_basenames() -> set[str]:
    """Mirror the extension-stripping rule in document_store.get_document_text."""
    names: set[str] = set()

    for yaml_path in [
        ROOT / "app/crews/notes_crew/data/reading_materials.yaml",
        ROOT / "app/crews/quiz_crew/data/reading_materials.yaml",
    ]:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        for vals in data.values():
            for v in vals:
                if v.startswith("http"):
                    continue
                names.add(v)

    eval_path = ROOT / "app/crews/assignment_crew/data/evaluation_documents.yaml"
    eval_data = yaml.safe_load(eval_path.read_text(encoding="utf-8"))
    activity_flags = {
        "Shoot", "shoot", "theory", "Practical class with acting dept",
        "in class exercise", "group discussion - culminated three modules above",
    }
    for v in eval_data.values():
        if v in activity_flags:
            continue
        names.add(v)

    out: set[str] = set()
    for n in names:
        lower = n.lower()
        for ext in (".pdf", ".docx", ".doc"):
            if lower.endswith(ext):
                n = n[: -len(ext)]
                break
        out.add(n + ".txt")
    return out


def list_bucket() -> set[str]:
    url = f"{SUPABASE_URL}/storage/v1/object/list/{BUCKET}"
    headers = {
        "Authorization": f"Bearer {SERVICE_KEY}",
        "apikey": SERVICE_KEY,
        "Content-Type": "application/json",
    }
    found: set[str] = set()
    offset = 0
    while True:
        body = {"prefix": "", "limit": 100, "offset": offset, "sortBy": {"column": "name", "order": "asc"}}
        r = httpx.post(url, json=body, headers=headers, timeout=30)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        for row in rows:
            found.add(row["name"])
        if len(rows) < 100:
            break
        offset += 100
    return found


def main() -> int:
    expected = expected_basenames()
    found = list_bucket()

    txts = {n for n in found if n.lower().endswith(".txt")}
    others = found - txts

    missing = sorted(expected - txts)
    extra_txts = sorted(txts - expected)

    print(f"Expected .txt files: {len(expected)}")
    print(f"Found in bucket:    {len(found)} total ({len(txts)} .txt, {len(others)} other)")
    print()

    if missing:
        print(f"MISSING ({len(missing)}):")
        for n in missing:
            print(f"  - {n}")
        print()
    else:
        print("All 33 expected .txt files are present.")
        print()

    if extra_txts:
        print(f"Extra .txt in bucket (not referenced by any crew, {len(extra_txts)}):")
        for n in extra_txts:
            print(f"  + {n}")
        print()

    if others:
        print(f"Non-txt files still in bucket ({len(others)}):")
        for n in sorted(others)[:50]:
            print(f"  . {n}")
        if len(others) > 50:
            print(f"  ... +{len(others)-50} more")

    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
