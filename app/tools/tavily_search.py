from __future__ import annotations

from typing import Any

import httpx
from crewai.tools import BaseTool

from app.config import get_settings


class TavilySearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for recent, relevant film/media examples. Input: a search query "
        "string. Returns the top result's title, URL, and content snippet."
    )

    def _run(self, query: str) -> str:
        settings = get_settings()
        if not settings.tavily_api_key:
            return "web_search unavailable: TAVILY_API_KEY not configured"

        body: dict[str, Any] = {
            "query": query,
            "topic": "general",
            "search_depth": "advanced",
            "chunks_per_source": 3,
            "max_results": 1,
            "days": 7,
            "include_answer": True,
            "include_raw_content": False,
        }
        headers = {"Authorization": f"Bearer {settings.tavily_api_key}"}

        try:
            r = httpx.post(
                "https://api.tavily.com/search", json=body, headers=headers, timeout=20
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            return f"web_search error: {exc}"

        data = r.json()
        if data.get("answer"):
            return str(data["answer"])
        results = data.get("results") or []
        if not results:
            return "web_search returned no results"
        top = results[0]
        return f"{top.get('title', '')}\n{top.get('url', '')}\n{top.get('content', '')}"


def build_tavily_tool() -> TavilySearchTool | None:
    settings = get_settings()
    if not settings.tavily_api_key:
        return None
    return TavilySearchTool()
