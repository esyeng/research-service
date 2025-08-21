from typing import List

async def run_subagent_tool(objective: str, search_focus: List[str], max_searches: int) -> dict:
    """Tool for the orchestrator to spawn a research subagent"""
    # First module to extract to subagent class
    return {}
    
async def web_search_tool(query: str) -> dict:
    """Direct web search capability for orchestrator"""
    return {}