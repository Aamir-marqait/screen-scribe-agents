from __future__ import annotations

import asyncio
import json
import re
from functools import lru_cache
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task

from app.config import get_settings

CREW_DIR = Path(__file__).parent
DATA_DIR = CREW_DIR / "data"


@lru_cache
def _load_yaml(name: str) -> dict:
    return yaml.safe_load((CREW_DIR / name).read_text(encoding="utf-8"))


@lru_cache
def _load_reading_materials() -> dict[str, list[str]]:
    return yaml.safe_load((DATA_DIR / "reading_materials.yaml").read_text(encoding="utf-8"))


def lookup_reading_materials(subtopic: str) -> list[str]:
    return _load_reading_materials().get(subtopic.strip().lower(), [])


def _extract_json(text: str) -> str:
    """Pull the first {...} JSON object out of a model response.

    The prompt asks the model to output bare JSON, but CrewAI sometimes wraps
    or pads the output. Be permissive on the way in, strict on the way out.
    """

    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


async def generate_quiz(subtopic: str) -> str:
    settings = get_settings()
    materials = lookup_reading_materials(subtopic)
    materials_block = ", ".join(materials) if materials else "(none assigned)"

    agent_cfg = _load_yaml("agents.yaml")["quiz_writer"]
    task_cfg = _load_yaml("tasks.yaml")["write_quiz"]

    agent = Agent(
        role=agent_cfg["role"],
        goal=agent_cfg["goal"],
        backstory=agent_cfg["backstory"],
        llm=settings.llm_model,
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description=task_cfg["description"].format(
            subtopic=subtopic,
            reading_materials=materials_block,
        ),
        expected_output=task_cfg["expected_output"],
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    raw = await asyncio.to_thread(crew.kickoff)

    # Frontend (CreateQuiz.tsx) expects { output: "<json string with all_questions[]>" }.
    # Validate that we have parseable JSON before returning, but return the JSON
    # *string* unchanged — the React parser does its own JSON.parse.
    payload = _extract_json(str(raw))
    parsed = json.loads(payload)
    if "all_questions" not in parsed:
        raise ValueError("quiz response missing 'all_questions' key")
    return json.dumps(parsed, ensure_ascii=False)
