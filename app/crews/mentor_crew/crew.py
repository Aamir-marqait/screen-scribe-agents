from __future__ import annotations

import asyncio
from collections import deque
from functools import lru_cache
from pathlib import Path
from threading import Lock

import yaml
from crewai import Agent, Crew, Process, Task

from app.config import get_settings

CREW_DIR = Path(__file__).parent
HISTORY_LIMIT = 12  # remembered turns per session


@lru_cache
def _load_yaml(name: str) -> dict:
    return yaml.safe_load((CREW_DIR / name).read_text(encoding="utf-8"))


# In-process session memory. Good enough for dev and small deployments;
# swap for Redis when we add the worker service for the script analyzer.
_SESSIONS: dict[str, deque[tuple[str, str]]] = {}
_SESSIONS_LOCK = Lock()


def _get_history(session_id: str | None) -> list[tuple[str, str]]:
    if not session_id:
        return []
    with _SESSIONS_LOCK:
        return list(_SESSIONS.get(session_id, deque()))


def _append_turn(session_id: str | None, user: str, assistant: str) -> None:
    if not session_id:
        return
    with _SESSIONS_LOCK:
        buf = _SESSIONS.setdefault(session_id, deque(maxlen=HISTORY_LIMIT))
        buf.append(("student", user))
        buf.append(("mentor", assistant))


def _format_history(turns: list[tuple[str, str]]) -> str:
    if not turns:
        return "(no prior messages in this session)"
    lines = []
    for speaker, text in turns:
        prefix = "Student:" if speaker == "student" else "Mentor:"
        lines.append(f"{prefix} {text}")
    return "\n".join(lines)


async def mentor_chat(chat_input: str, session_id: str | None = None) -> str:
    settings = get_settings()
    agent_cfg = _load_yaml("agents.yaml")["academic_mentor"]
    task_cfg = _load_yaml("tasks.yaml")["chat_with_student"]

    agent = Agent(
        role=agent_cfg["role"],
        goal=agent_cfg["goal"],
        backstory=agent_cfg["backstory"],
        llm=settings.llm_model,
        allow_delegation=False,
        verbose=False,
    )
    history = _get_history(session_id)
    task = Task(
        description=task_cfg["description"].format(
            chat_input=chat_input,
            history=_format_history(history),
        ),
        expected_output=task_cfg["expected_output"],
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = await asyncio.to_thread(crew.kickoff)
    response = str(result).strip()
    _append_turn(session_id, chat_input, response)
    return response
