import os
import aiohttp
import httpx
import json
from typing import List
from .data_methods import prune_brave_search_json
from ..utils.types import SubTaskResult
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    v = os.getenv(name)
    if v is None or not v.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v.strip()


BRAVE_SEARCH_API_KEY = require_env("BRAVE_SEARCH_API_KEY")
API_URL = "https://api.search.brave.com/res/v1/web/search"
API_HEADERS = {
    "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
    "Accept": "application/json",
}


async def web_fetch(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Fetch failed {resp.status} for {url}")
            return await resp.text()


async def web_search(
    query: str,
    max_results: int = 10,
) -> str:
    """Direct web search capability using Brave Search API for orchestrator"""
    params = {"q": query, "count": max_results, "country": "us", "search_lang": "en"}
    print(f"\n\n!! WE FINNA SEARCH UP THIS SHIEE -~-~> {query}")
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, headers=API_HEADERS, params=params) as resp:
            print('raw')
            raw = await resp.json()
            print(raw)
            data = prune_brave_search_json(raw, 5)
            if resp.status != 200:
                raise RuntimeError(f"Brave Search API error {resp.status}: {data}")
            return json.dumps(data)


def complete_task(
    insights: str,
    findings: List[str],
    sources: List[str],
    confidence: float = 0.8,
):
    print(f"running complete_task")
    return SubTaskResult(
        task_complete=True,
        insights=insights,
        findings=findings,
        sources=sources,
        confidence=confidence,
    )


async def wikipedia(q):
    print(f"about to search wikipedia w/query: {q}")
    async with httpx.AsyncClient() as client:
        result = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": q,
                "format": "json",
            },
        )
    return result.json()["query"]["search"][0]["snippet"]
