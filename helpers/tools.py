import os
import aiohttp
import asyncio
import httpx
import json

# from newspaper import Article
from typing import List, Dict, Any, Optional
from utils.types import SubTaskResult
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


def prune_brave_search_json(
    search_data: Dict[str, Any], max_results: Optional[int] = 10
) -> Dict[str, Any]:
    """
    returns structured JSON of brave search results
    """
    query_info = search_data.get("query", {})
    pruned_data = {
        "query": query_info.get("original", ""),
        "web_results": [],
        "video_results": [],
    }
    # Process web results
    web_data = search_data.get("web", {})
    if web_data and "results" in web_data:
        web_results = (
            web_data["results"][:max_results] if max_results else web_data["results"]
        )
        for result in web_results:
            pruned_data["web_results"].append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "description": result.get("description", ""),
                    "source": result.get("profile", {}).get("name", ""),
                    "age": result.get("age", ""),
                    "content_type": result.get("subtype", "generic"),
                }
            )

    # Process video results
    video_data = search_data.get("videos", {})
    if video_data and "results" in video_data:
        for video in video_data["results"]:
            video_info = video.get("video", {})
            pruned_data["video_results"].append(
                {
                    "title": video.get("title", ""),
                    "url": video.get("url", ""),
                    "description": video.get("description", ""),
                    "creator": video_info.get("creator", ""),
                    "duration": video_info.get("duration", ""),
                    "age": video.get("age", ""),
                    "platform": video_info.get("publisher", ""),
                }
            )

    return pruned_data


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
) -> str:
    """Direct web search capability using Brave Search API for orchestrator"""

    params = {"q": query, "count": max_results, "country": "us", "search_lang": "en"}
    print(f"\n\n!! WE FINNA SEARCH UP THIS SHIEE -~-~> {query}")
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, headers=API_HEADERS, params=params) as resp:
            raw = await resp.json()
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


# def extract_text(url: str):
#     article = Article(url)
#     article.download()
#     article.parse()
#     return article.text
