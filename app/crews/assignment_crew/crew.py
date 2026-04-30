from __future__ import annotations

import asyncio
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
def _load_evaluation_documents() -> dict[str, str]:
    return yaml.safe_load((DATA_DIR / "evaluation_documents.yaml").read_text(encoding="utf-8"))


def lookup_evaluation_document(subtopic: str) -> str:
    docs = _load_evaluation_documents()
    return docs.get(subtopic.strip().lower(), "(none assigned)")


def _build_agent() -> Agent:
    settings = get_settings()
    cfg = _load_yaml("agents.yaml")["assignment_designer"]
    return Agent(
        role=cfg["role"],
        goal=cfg["goal"],
        backstory=cfg["backstory"],
        llm=settings.llm_model,
        allow_delegation=False,
        verbose=False,
    )


async def generate_assignment(subtopic: str) -> str:
    agent = _build_agent()
    tasks_cfg = _load_yaml("tasks.yaml")["generate_assignment"]
    task = Task(
        description=tasks_cfg["description"].format(
            subtopic=subtopic,
            evaluation_document=lookup_evaluation_document(subtopic),
        ),
        expected_output=tasks_cfg["expected_output"],
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = await asyncio.to_thread(crew.kickoff)
    return str(result)


async def revise_assignment(subtopic: str, content: str, changes: str) -> str:
    agent = _build_agent()
    tasks_cfg = _load_yaml("tasks.yaml")["revise_assignment"]
    task = Task(
        description=tasks_cfg["description"].format(
            subtopic=subtopic,
            evaluation_document=lookup_evaluation_document(subtopic),
            content=content,
            changes=changes,
        ),
        expected_output=tasks_cfg["expected_output"],
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = await asyncio.to_thread(crew.kickoff)
    return str(result)
