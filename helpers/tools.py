import os
import aiohttp
import asyncio
import httpx
import json
# from newspaper import Article
from typing import List
from helpers.llmclient import require_env

BRAVE_SEARCH_API_KEY = require_env("BRAVE_SEARCH_API_KEY")
API_URL = "https://api.search.brave.com/res/v1/web/search"
API_HEADERS = {
    "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
    "Accept": "application/json",
}


async def run_subagent_tool(
    objective: str, search_focus: List[str], max_searches: int
) -> dict:
    """Tool for the orchestrator to spawn a research subagent"""
    # First module to extract to subagent class
    return {}


async def web_fetch(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Fetch failed {resp.status} for {url}")
            return await resp.text()


async def web_search(
    query: str,
    max_results: int = 10,
) -> dict:
    """Direct web search capability using Brave Search API for orchestrator"""

    params = {"q": query, "count": max_results, "country": "us", "search_lang": "en"}

    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, headers=API_HEADERS, params=params) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"Brave Search API error {resp.status}: {data}")
            return data


async def wikipedia(q):
    print(f"about to search wikipedia w/query: {q}")
    async with httpx.AsyncClient() as client:
        result = await client.get("https://en.wikipedia.org/w/api.php", params={
        "action": "query",
        "list": "search",
        "srsearch": q,
        "format": "json"
    })
    return result.json()["query"]["search"][0]["snippet"]


# def extract_text(url: str):
#     article = Article(url)
#     article.download()
#     article.parse()
#     return article.text