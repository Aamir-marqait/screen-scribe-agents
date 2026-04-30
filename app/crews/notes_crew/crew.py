from __future__ import annotations

import asyncio
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task

from app.config import get_settings
from app.tools.tavily_search import build_tavily_tool

CREW_DIR = Path(__file__).parent
DATA_DIR = CREW_DIR / "data"


@lru_cache
def _load_yaml(name: str) -> dict:
    return yaml.safe_load((CREW_DIR / name).read_text(encoding="utf-8"))


@lru_cache
def _load_reading_materials() -> dict[str, list[str]]:
    return yaml.safe_load((DATA_DIR / "reading_materials.yaml").read_text(encoding="utf-8"))


def lookup_reading_materials(subtopic: str) -> list[str]:
    materials = _load_reading_materials()
    return materials.get(subtopic.strip().lower(), [])


def _build_crew(subtopic: str, reading_materials: list[str]) -> Crew:
    settings = get_settings()
    agents_cfg = _load_yaml("agents.yaml")
    tasks_cfg = _load_yaml("tasks.yaml")

    materials_block = ", ".join(reading_materials) if reading_materials else "(none assigned)"

    tools = []
    tavily = build_tavily_tool()
    if tavily is not None:
        tools.append(tavily)

    writer = Agent(
        role=agents_cfg["notes_writer"]["role"],
        goal=agents_cfg["notes_writer"]["goal"],
        backstory=agents_cfg["notes_writer"]["backstory"],
        llm=settings.llm_model,
        tools=tools,
        allow_delegation=False,
        verbose=False,
    )

    task = Task(
        description=tasks_cfg["write_notes"]["description"].format(
            subtopic=subtopic,
            reading_materials=materials_block,
            reading_materials_inline=materials_block,
            current_year=datetime.utcnow().year,
        ),
        expected_output=tasks_cfg["write_notes"]["expected_output"],
        agent=writer,
    )

    return Crew(agents=[writer], tasks=[task], process=Process.sequential, verbose=False)


async def generate_notes(subtopic: str) -> str:
    """Generate markdown study notes for a subtopic.

    Returns the markdown body. Caller wraps it as ``{ "output": <markdown> }``
    to match the n8n response shape consumed by ``CreateNotes.tsx``.
    """

    reading_materials = lookup_reading_materials(subtopic)
    crew = _build_crew(subtopic, reading_materials)
    result = await asyncio.to_thread(crew.kickoff, inputs={"subtopic": subtopic})
    return str(result)
