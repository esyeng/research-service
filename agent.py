import datetime
import asyncio
import random
import json
import time
from typing import List, Callable
from helpers.llmclient import LLMClient, extract_json_from_markdown
from helpers.tools import web_search, web_fetch, complete_task
from prompts.make import plan, pretty
from utils.types import (
    SubTask,
    SubTaskResult,
    TaskPlan,
    ResourceConfig,
    OrchestratorError,
    TaskDecompositionError,
)
from prompts.research_subagent import txt as research_subagent_prompt


class SearchBot:
    TIMEOUT = 240
    CONVERSATION_TIMEOUT = 800

    def __init__(self, task: SubTask):
        self.client = LLMClient()
        self.task = task
        self.system = "You are an expert researcher"
        self.tools = []
        self.sources = []
        self.snippets = []

    def _build_prompt(self, tools_available: List[str]):
        today = datetime.date.today().isoformat()
        prompt = f"""
        You are a research agent working as part of a team. The current date is {today}.
        Your goal is to surface high quality sources and findings in the form of quotes, exerpts, and articles. You should use discernment to select material relevant to the main objective. Your output should be sources, and snippets from them that are relevant. The ONLY time you may put things in your own words when describing why something could be useful or relevant, otherwise you should ALWAYS quote/produce source materials exactly as they appear in the sources directly
        
        <task>
        Objective: {self.task.objective}
        Expected Output: {self.task.expected_output}
        Suggested Starting Points: {self.task.search_focus}
        Research Budget: 2 - 5 tool calls
        </task>
        
        <research_process>
        1. **Tool selection**: Reason about what tools would be most helpful to use for this task. Use the right tools when a task implies they would be helpful. The user has provided these tools to help you answer their queries well.
        - ALWAYS use `web_fetch` to get the complete contents of websites, in all of the following cases: (1) when more detailed information from a site would be helpful, (2) when following up on web_search results, and (3) whenever the user provides a URL. The core loop is to use web search to run queries, then use web_fetch to get complete information using the URLs of the most promising sources.
        - Avoid using the use your own reasoning to do things like count entities.
        2. **Research loop**: Execute an excellent OODA (observe, orient, decide, act) loop by (a) observing what information has been gathered so far, what still needs to be gathered to accomplish the task, and what tools are available currently; (b) orienting toward what tools and queries would be best to gather the needed information and updating beliefs based on what has been learned so far; (c) making an informed, well-reasoned decision to use a specific tool in a certain way; (d) acting to use this tool. Repeat this loop in an efficient way to research well and learn based on new results.
        - Execute a MINIMUM of five distinct tool calls, up to ten for complex queries. Avoid using more than ten tool calls.
        - Reason carefully after receiving tool results. Make inferences based on each tool result and determine which tools to use next based on new findings in this process. Evaluate the quality of the sources in search results carefully. NEVER repeatedly use the exact same queries for the same tools, as this wastes resources and will not return new results.
        3. **Content extraction**: With the sources you're determined are most relevant to the research objective, extract quotes, snippets, and passages VERBATIM and organize them into an evidence report for the lead researcher to ingest and reference.
        - Prioritize evidence-backed, reputable sources and aim to extract sections of their contents that would be pertinent to have in a final report to the user who prefers human-written primary information rather than AI summarized information.
        - When something stands out to you as relevant or important, be sure to note and express what it is and where you found it.
        Follow this process well to complete the task. Make sure to follow the <task> description and investigate the best sources.
        </research_process>
        <think_about_source_quality>
        After receiving results from web searches or other tools, think critically, reason about the results, and determine what to do next. Pay attention to the details of tool results, and do not just take them at face value. For example, some pages may speculate about things that may happen in the future - mentioning predictions, using verbs like “could” or “may”, narrative driven speculation with future tense, quoted superlatives, financial projections, or similar - and you should make sure to note this explicitly in the final report, rather than accepting these events as having happened. Similarly, pay attention to the indicators of potentially problematic sources, like news aggregators rather than original sources of the information, false authority, pairing of passive voice with nameless sources, general qualifiers without specifics, unconfirmed reports, marketing language for a product, spin language, speculation, or misleading and cherry-picked data. Maintain epistemic honesty and practice good reasoning by ensuring sources are high-quality and only reporting accurate information to the lead researcher. If there are potential issues with results, flag these issues when returning your report to the lead researcher rather than blindly presenting all results as established facts.
        </think_about_source_quality>

        <use_parallel_tool_calls>
        For maximum efficiency, whenever you need to perform multiple independent operations, invoke 2 relevant tools simultaneously rather than sequentially. Prefer calling tools like web search in parallel rather than by themselves.
        </use_parallel_tool_calls>

        <maximum_tool_call_limit> To prevent overloading the system, it is required that you stay under a limit of 20 tool calls and under about 100 sources. This is the absolute maximum upper limit. If you exceed this limit, the subagent will be terminated. Therefore, whenever you get to around 15 tool calls or 70 sources, make sure to stop gathering sources, and instead use the complete_task tool immediately. Avoid continuing to use tools when you see diminishing returns - when you are no longer finding new relevant information and results are not getting better, STOP using tools and instead compose your final result of noteworthy insights and findings. </maximum_tool_call_limit>
        <important>Make sure to terminate research when it is no longer necessary, to avoid wasting time and resources!!</important>
        Follow the <research_process> and the <research_guidelines> above to accomplish the task, making sure to parallelize tool calls for maximum efficiency. Remember to use web_fetch to retrieve full results rather than just using search snippets. Continue using the relevant tools until this task has been fully accomplished, all necessary information has been gathered, and you are ready to report the results to the lead research agent. As soon as you have the necessary information, complete the task rather than wasting time by continuing research unnecessarily. As soon as the task is done, immediately use the `complete_task` tool to finish and provide your insights and findings to the lead researcher.
        
        Available tools: {", ".join(tools_available)}
        Exexute your task using the tools you have access to
        
        <result_format>
        Output your results as JSON:
        {{
            "sources": [
                "<url_result_0>",
                "<url_result_1>",
                "<url_result_2>,
                ..etc.
            ],
            "snippets": [
                {{
                    "kind": "quote",
                    "text": "<direct_quote_from_source>...",
                    "link": "<url>"
                }},
                {{
                    "kind": "article",
                    "text": "<full_text_of_article>...",
                    "link": "<url>"
                }},
                {{
                    "kind": "exerpt",
                    "text": "<extracted_text_from_source>...",
                    "link": "<url>"
                }},
                {{
                    "kind": "media",
                    "summary": "describe what this media is or contains",
                    "link": "<url_of_img_or_video>..etc"
                }}
            ]
        }}
        </result_format>
        """
        return prompt

    def _make_web_fetch_tool(self):
        """Tool for subagents to fetch full webpage content"""
        return {
            "name": "web_fetch",
            "description": "Get complete webpage content from URLs found in search results. Use this after web searches to get detailed information.",
            "function": web_fetch,
            "parameters": {
                "url": {
                    "type": "string",
                    "description": "URL from search results to fetch full content",
                }
            },
        }

    def _make_web_search_tool(self):
        return {
            "name": "web_search",
            "description": "Search the web for information",
            "function": web_search,
            "parameters": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return",
                    "default": 10,
                },
            },
        }

    def _make_complete_task_tool(self):
        """Tool for subagents to signal completion"""

        return {
            "name": "complete_task",
            "description": "Provide comprehensive research results organizing and compiling all findings. Call this when research subtasks have been completed and you have sufficient information to hand off to the lead researcher.",
            "function": complete_task,
            "parameters": {
                "insights": {
                    "type": "string",
                    "description": "Breakdown of key observations, notable discoveries, and important considerations you'd like to mention or share based on what you've analyzed",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Collection of quotes, page sections, snippets, facts, or details most relevant to the research task that the lead researcher should have access to",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of sources used",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in findings (0-1)",
                },
            },
        }

    def _normalize_orchestrator_result(self, res: object) -> dict:
        """
        Collapse whatever the orchestrator returned into a stable shape.
        Handles minor field spelling issues like 'tool_calls_' vs 'tool_calls_count'.
        """
        if not isinstance(res, dict):
            return {
                "status": "completed",
                "final_response": str(res),
                "tool_calls_used": 0,
                "raw_conversation": [],
                "error": None,
            }

        tool_calls_used = res.get("tool_calls_count") or res.get("tool_calls_") or 0

        status = "error" if res.get("error") else "completed"

        return {
            "status": status,
            "final_response": res.get("final_response", ""),
            "tool_calls_used": int(tool_calls_used),
            "raw_conversation": res.get("conversation", []),
            "error": res.get("error"),
        }

    async def _execute(self) -> dict:
        """Execute a single subagent using subagent prompt"""
        print(
            f"executing single subagent on task: {self.task.id} -> {self.task.objective}"
        )

        subagent_prompt = self._build_prompt(
            tools_available=["web_search", "web_fetch", "complete_task"]
        )

        # Prepare the tool definitions
        subagent_tools_list = [
            self._make_web_search_tool(),
            self._make_web_fetch_tool(),
            self._make_complete_task_tool(),
        ]

        # Convert list of tool dicts into name -> function mapping for orchestrator
        tool_functions: dict[str, Callable] = {
            t["name"]: t["function"] for t in subagent_tools_list
        }

        start = time.monotonic()

        try:
            result = await self.client.call_llm_with_tools(
                prompt=subagent_prompt,
                system=self.system,
                tools=subagent_tools_list,  # pass list for call_llm_with_tools, works with new refactor
                model="claude-3-5-haiku-20241022",
                timeout=self.TIMEOUT,
                conversation_timeout=self.CONVERSATION_TIMEOUT,
            )

            # Now normalize the output
            out = self._normalize_orchestrator_result(result)
            out["task_id"] = self.task.id
            out["latency_ms"] = int((time.monotonic() - start) * 1000)
            return out

        except asyncio.TimeoutError:
            return {
                "task_id": self.task.id,
                "status": "timeout",
                "final_response": "Subagent execution timed out",
                "tool_calls_used": 0,
                "raw_conversation": [],
                "error": f"Exceeded {self.TIMEOUT}s timeout",
                "latency_ms": int((time.monotonic() - start) * 1000),
            }

        except Exception as e:
            return {
                "task_id": self.task.id,
                "status": "error",
                "final_response": "...",
                "tool_calls_used": 0,
                "raw_conversation": [],
                "error": str(e),
                "latency_ms": int((time.monotonic() - start) * 1000),
            }


"""
Simplicity refactor ->

Using one agent
Hard code agent to write a specific report using search and fetch

Immediate next steps:

Write an example report (what I want to see emailed to me)

Then write the prompt with the research question for the agent to gather research materials to satisfy the question -> uses search

Then in a separate API call,
Pass in the research materials and the example report
   This should prompt the agent to use fetch to mine for examples, then output final report
"""
