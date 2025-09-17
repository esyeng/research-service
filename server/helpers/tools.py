import os
import aiohttp
import httpx
import json
from typing import List, Dict, Any
from .data_methods import prune_brave_search_json
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


async def web_fetch(url: str) -> str:
    """
    Fetch complete webpage content from a URL.
    Returns plain text content of the webpage.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Fetch failed {resp.status} for {url}")
                return await resp.text()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch {url}: {str(e)}")


async def web_search(
    query: str,
    max_results: int = 10,
) -> Dict[str, Any]:
    """
    Search the web using Brave Search API.
    Returns structured data with search results.
    """
    params = {"q": query, "count": max_results, "country": "us", "search_lang": "en"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                API_URL,
                headers=API_HEADERS,
                params=params,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(
                        f"Brave Search API error {resp.status}: {error_text}"
                    )

                raw_data = await resp.json()
                return prune_brave_search_json(raw_data, max_results)

    except Exception as e:
        raise RuntimeError(f"Web search failed for query '{query}': {str(e)}")


async def check_search_health() -> bool:
    """Check if the Brave Search API is accessible"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                API_URL,
                headers=API_HEADERS,
                params={"q": "test", "count": 1},
                timeout=10,
            ) as resp:
                return resp.status == 200
    except:
        return False
