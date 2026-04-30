from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from crewai import Agent, Crew, Process, Task

from app.config import get_settings

CREW_DIR = Path(__file__).parent

# Mirrors the n8n Differentiator Code node, with one important difference:
# the n8n IF node had an empty false-branch, which silently dropped sem-type
# requests. Here both branches actually run.
SEM_TYPES = {"documentary", "shortfilm", "feature film", "episodic content"}

ScheduleType = Literal["weekly", "sem"]


@lru_cache
def _load_yaml(name: str) -> dict:
    return yaml.safe_load((CREW_DIR / name).read_text(encoding="utf-8"))


def classify_type(type_value: str | None) -> ScheduleType | None:
    if not type_value:
        return None
    if type_value == "assignment":
        return "weekly"
    if type_value in SEM_TYPES:
        return "sem"
    return None


async def analyze_script(script_text: str, schedule: ScheduleType) -> str:
    settings = get_settings()
    agents_cfg = _load_yaml("agents.yaml")
    tasks_cfg = _load_yaml("tasks.yaml")

    if schedule == "weekly":
        agent_key = "script_mentor_weekly"
        task_key = "analyze_script_weekly"
    else:
        agent_key = "script_mentor_semester"
        task_key = "analyze_script_semester"

    agent_cfg = agents_cfg[agent_key]
    task_cfg = tasks_cfg[task_key]

    agent = Agent(
        role=agent_cfg["role"],
        goal=agent_cfg["goal"],
        backstory=agent_cfg["backstory"],
        llm=settings.llm_model,
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description=task_cfg["description"].format(script_text=script_text),
        expected_output=task_cfg["expected_output"],
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = await asyncio.to_thread(crew.kickoff)
    return str(result)
