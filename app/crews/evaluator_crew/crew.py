from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task

from app.config import get_settings
from app.crews.assignment_crew.crew import lookup_evaluation_document

CREW_DIR = Path(__file__).parent


@lru_cache
def _load_yaml(name: str) -> dict:
    return yaml.safe_load((CREW_DIR / name).read_text(encoding="utf-8"))


async def evaluate_submission(
    *,
    criteria: str,
    subtopic: str,
    submission_text: str,
) -> str:
    settings = get_settings()
    agent_cfg = _load_yaml("agents.yaml")["academic_evaluator"]
    task_cfg = _load_yaml("tasks.yaml")["evaluate_submission"]

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
            criteria=criteria,
            subtopic=subtopic,
            evaluation_document=lookup_evaluation_document(subtopic),
            submission_text=submission_text,
        ),
        expected_output=task_cfg["expected_output"],
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = await asyncio.to_thread(crew.kickoff)
    return str(result)
