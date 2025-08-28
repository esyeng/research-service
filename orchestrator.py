import datetime
import asyncio
import random
import json
from typing import List
from helpers.llmclient import (
    stream_llm_sync,
    extract_json_from_markdown,
    llm_call_with_tools,
)
from helpers.tools import web_search, web_fetch
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


class ResearchOrchestrator:
    """Orchestrates the decomposition and allocation of research queries into actionable sub-tasks for AI research agents.
    Attributes:
        MAX_SUBAGENTS (int): Maximum number of sub-agents allowed per query.
        MAX_SEARCHES_PER_AGENT (int): Maximum number of searches each sub-agent can perform.
        SUBAGENT_TIMEOUT (int): Timeout in seconds for each sub-agent's task.
        memory (list): Internal memory for storing orchestrator state or history.
    Methods:
        __init__():
            Initializes the orchestrator and its memory.
        _allocate_resources(complexity_score: int, orchestrate: bool = False) -> ResourceConfig | str:
            Allocates resources and selects model configuration based on query complexity.
        _build_task_plan(**kwargs) -> str:
            Constructs the LLM prompt for analyzing and decomposing a research query.
        _build_subagent_prompt(self, subtask: SubTask, tools_available: List[str]) -> str:
            Build focused subagent prompt using Anthropic's template
        _parse_and_validate(raw_response: str | dict) -> TaskPlan:
            Parses and validates the LLM output, ensuring it meets required structure and rules.
        _estimate_subtask_complexity(self, subtask: SubTask) -> int:
            estimate subtask complexity for budget setting
        analyze_query(query: str):
            Main entry point for analyzing a research query, generating a prompt, invoking the LLM, and returning a validated TaskPlan.
    """

    MAX_SUBAGENTS = 5
    MAX_SEARCHES_PER_AGENT = 10
    SUBAGENT_TIMEOUT = 120
    CONVERSATION_TIMEOUT = 600

    def __init__(self):
        self.memory = []

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

    def _make_run_subagent_tool(self, task_plan: TaskPlan):
        async def run_subagent(subtask_id: str, custom_instructions: str | None = None):
            # subagent execution logic here
            subtask = next(st for st in task_plan.subtasks if st.id == subtask_id)

            # execute subagent
            result = await self._execute_single_subagent(subtask, custom_instructions)
            print(f"ran_subagent on task: {subtask_id}")
            return result

        return {
            "name": "run_subagent",
            "description": f"Execute a research subtask. Available subtasks: {[st.id + ': ' + st.objective for st in task_plan.subtasks]}",
            "function": run_subagent,
            "parameters": {
                "subtask_id": {
                    "type": "string",
                    "description": "ID of the subtask to execute",
                    "enum": [st.id for st in task_plan.subtasks],
                },
                "custom_instructions": {
                    "type": "string",
                    "description": "Additional specific instructions for this subagent",
                    # "required": False,
                },
            },
        }

    def _make_complete_task_tool(self):
        """Tool for subagents to signal completion"""

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

    def _estimate_subtask_complexity(self, subtask: SubTask) -> int:
        """Quick heuristic to estimate subtask complexity for budget setting"""
        if len(subtask.search_focus) <= 2 and len(subtask.objective.split()) <= 10:
            return 1
        elif len(subtask.search_focus) <= 4 and len(subtask.objective.split()) <= 20:
            return 2
        else:
            return 3

    def _select_model(self, complexity_score: int = 1):
        model_choices = {
            "straightforward": "claude-3-5-haiku-20241022",
            "moderate": "claude-3-7-sonnet-20250219",
            "complex": "claude-sonnet-4-20250514",
        }
        simp = complexity_score == 1
        mid = complexity_score == 2
        return (
            model_choices["straightforward"]
            if simp
            else model_choices["moderate"] if mid else model_choices["complex"]
        )

    def _allocate_resources(self, task_plan: TaskPlan) -> ResourceConfig:
        model_choices = {
            "straightforward": "claude-3-5-haiku-20241022",
            "moderate": "claude-3-7-sonnet-20250219",
            "complex": "claude-sonnet-4-20250514",
        }
        simp = task_plan.complexity_score == 1
        mid = task_plan.complexity_score == 2
        if task_plan.complexity_score > 3:
            raise OrchestratorError("Complexity score out of range")

        return ResourceConfig(
            max_subagents=1 if simp else 3 if mid else 4,
            searches_per_agent=4 if simp else 7 if mid else 12,
            model_per_task=(
                model_choices["straightforward"] if simp else model_choices["moderate"]
            ),
            total_token_budget=12000 if simp else 16000,
            timeout_seconds=60 if simp else 120,
        )

    def _build_subagent_prompt(
        self, subtask: SubTask, tools_available: List[str]
    ) -> str:
        """Build focused subagent prompt using template"""

        # adapt complexity to tool call budget
        complexity_to_budget = {
            1: "under 4 tool calls",  # simple
            2: "4-7 tool calls",  # medium
            3: "8-12 tool calls",  # complex
        }
        today = datetime.date.today().isoformat()

        # prompt with task injected
        return f"""
        You are a research subagent working as part of a team. The current date is {today}. 

        <task>
        Objective: {subtask.objective}
        Expected Output: {subtask.expected_output}
        Suggested Starting Points: {subtask.search_focus}
        Research Budget: {complexity_to_budget.get(self._estimate_subtask_complexity(subtask), "3-7 tool calls")}
        </task>

            {research_subagent_prompt} 

        Available tools: {", ".join(tools_available)}
        Exexute your task using the tools you have access to, 
        """

    async def _execute_single_subagent(
        self, subtask: SubTask, custom_instructions: str | None = None
    ) -> dict:
        """Execute a single subagent using subagent prompt"""
        print(f"executing single subagent on task: {subtask.id} -> {subtask.objective}")

        subagent_prompt = self._build_subagent_prompt(
            subtask, tools_available=["web_search", "web_fetch", "complete_task"]
        )

        # add custom instructions if provided by orchestrator
        if custom_instructions:
            subagent_prompt += f"\n\nAdditional instructions from lead researcher: {custom_instructions}"

        # execute subagent with its own tool set
        subagent_tools = [
            self._make_web_search_tool(),
            self._make_web_fetch_tool(),
            self._make_complete_task_tool(),
        ]

        try:
            result = await llm_call_with_tools(
                prompt=subagent_prompt,
                tools=subagent_tools,
                model=self._select_model(
                    subtask.max_search_calls // 5
                ),  # Rough complexity
                timeout=self.SUBAGENT_TIMEOUT,
                conversation_timeout=self.CONVERSATION_TIMEOUT,
            )
            if result and type(result) == dict:
                
                return {
                    "subtask_id": subtask.id,
                    "status": "completed",
                    "findings": result.get("final_response", ""),
                    "tool_calls_used": result.get("tool_calls_count", 0),
                    "raw_conversation": result.get("conversation", []),
                }
            else:
                return {
                    "subtask_id": subtask.id,
                    "status": "completed",
                    "findings": result["final_response"],
                    "tool_calls_used": result["tool_calls_count"],
                    "raw_conversation": result["conversation"],
                }
        except asyncio.TimeoutError:
            return {
                "subtask_id": subtask.id,
                "status": "timeout",
                "findings": "Subagent execution timed out",
                "tool_calls_used": 0,
                "error": f"Exceeded {self.SUBAGENT_TIMEOUT}s timeout",
            }
        except Exception as e:
            return {
                "subtask_id": subtask.id,
                "status": "error",
                "findings": "",
                "tool_calls_used": 0,
                "error": str(e),
            }

    def _parse_and_validate(self, raw_response: str | dict) -> TaskPlan:
        """
        Parse LLM output into a TaskPlan and validate structure/rules.
        Raises TaskDecompositionError on any failure.
        """
        if isinstance(raw_response, dict):
            plan_dict = raw_response
        else:
            try:
                plan_dict = extract_json_from_markdown(raw_response)
            except Exception as e:
                raise TaskDecompositionError(f"Invalid JSON from LLM: {e}")

        # Required fields
        required_fields = ["strategy", "complexity", "subtasks"]
        for f in required_fields:
            if f not in plan_dict:
                raise TaskDecompositionError(f"Missing required field '{f}' in plan")

        subtasks = []
        if len(plan_dict["subtasks"]) > self.MAX_SUBAGENTS:
            plan_dict["subtasks"] = plan_dict["subtasks"][: self.MAX_SUBAGENTS]

        for i, st in enumerate(plan_dict["subtasks"], start=1):
            if i > self.MAX_SUBAGENTS:
                break  # enforce max

            # Validate subtask fields
            if "objective" not in st or "expected_output" not in st:
                raise TaskDecompositionError(f"Invalid subtask definition: {st}")

            subtasks.append(
                SubTask(
                    id=st.get("id", f"task_{i:03d}"),
                    objective=st["objective"],
                    search_focus=st.get("search_queries", []),
                    expected_output=st["expected_output"],
                    priority=st["priority"],
                    max_search_calls=min(
                        st.get("max_searches", 1),
                        self.MAX_SEARCHES_PER_AGENT,
                    ),
                )
            )

        if not subtasks:
            raise TaskDecompositionError("No valid subtasks produced by LLM")

        if len(subtasks) > self.MAX_SUBAGENTS:
            raise TaskDecompositionError("Subtasks created exceeds max allowed")

        return TaskPlan(
            strategy=plan_dict["strategy"],
            query_type=plan_dict["query_type"],
            subtasks=subtasks,
            complexity_score=plan_dict.get("complexity", 1),
        )

    def analyze_query(self, query: str):
        plan_json = plan(query=query, current_date=datetime.date.today())
        raw = stream_llm_sync(query, plan_json)
        return self._parse_and_validate(raw)

    async def execute_research(self, query: str) -> dict:
        """Main research flow with orchestrated tool-calling"""
        task_plan = self.analyze_query(query)
        resource_config = self._allocate_resources(task_plan)
        spec = f"""
        - Max Subagents: {resource_config.max_subagents}
        - Searches Per Agent: {resource_config.searches_per_agent}
        - Model Per Task: {resource_config.model_per_task}
        """
        print(f"spec: {spec}")
        orchestration_prompt = f"""
        You are an AI research orchestrator armed with a team of subagent researchers. You are tasked with executing the following research plan for the provided query:

        Original Query: {query}
        Strategy: {task_plan.strategy}
        Query Type: {task_plan.query_type}
        Subtasks: {len(task_plan.subtasks)} parallel tasks
        Subagent specifications: {spec}

        Your job:
        1. Use run_subagent tool for each subtask in parallel
        2. Monitor progress and wait for all subtasks to complete
        3. Synthesize all subtask results into a comprehensive report
        4. Use complete_task when done

        Key constraints from planning:
        - Maximum {len(task_plan.subtasks)} subagents
        - Each subtask has specific boundaries to prevent overlap

        Execute the plan now using parallel subagent calls. Keep going until you are ready to report your findings, at which point you will use complete_task, passing in all of your findings, sources, and confidence scores.
        
        CRITICAL CHECKLIST - Complete ALL items:
        □ Run subagents for each subtask  
        □ each subagent should:
            □ Get search results
            □ Use web_fetch on 3-5 most promising URLs from search results
            □ Use complete_task, returning findings, sources, and confidence_score
        □ Use complete_task using all subagent complete_task results to generate a cited comprehensive report. Reflect on your analysis of the data and write a report that uses quotes and tells an evidence-backed narrative
        
        <important_guidelines>
        In communicating with subagents, maintain extremely high information density while being concise - describe everything needed in the fewest words possible.
        As you progress through the search process:
        1. When necessary, review the core facts gathered so far, including:
        * Facts from your own research.
        * Facts reported by subagents.
        * Specific dates, numbers, and quantifiable data.
        2. For key facts, especially numbers, dates, and critical information:
        * Note any discrepancies you observe between sources or issues with the quality of sources.
        * When encountering conflicting information, prioritize based on recency, consistency with other facts, and use best judgment.
        3. Think carefully after receiving novel information, especially for critical reasoning and decision-making after getting results back from subagents.
        4. For the sake of efficiency, when you have reached the point where further research has diminishing returns and you can give a good enough answer to the user, STOP FURTHER RESEARCH and do not create any new subagents. Just write your final report at this point. Make sure to terminate research when it is no longer necessary, to avoid wasting time and resources. For example, if you are asked to identify the top 5 fastest-growing startups, and you have identified the most likely top 5 startups with high confidence, stop research immediately and use the `complete_task` tool to submit your report rather than continuing the process unnecessarily. 
        5. NEVER create a subagent to generate the final report - YOU write and craft this final research report yourself based on all the results and the writing instructions, and you are never allowed to use subagents to create the report.
        </important_guidelines>

        """
        # print(f"orc prompt? {orchestration_prompt}")
        subagent_tools = [
            self._make_complete_task_tool(),
            self._make_run_subagent_tool(task_plan),
        ]

        # This is where the magic happens - LLM manages the flow
        result = await llm_call_with_tools(
            orchestration_prompt,
            tools=subagent_tools,
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            timeout=600,
        )
        # claude-sonnet-4-20250514
        # claude-opus-4-1-20250805
        # print(result)
        print(f"result keys? {result.keys()}")
        print(f"final_response: {result['final_response']}")
        if result:
            self.record_memories(result["conversation"])
        return result

    def record_memories(self, conversation):
        for message in conversation:
            self.memory.append(message)
        for i, message in enumerate(self.memory):
            with open("output.txt", "w") as f:
                f.writelines(
                    [
                        f"conversation length: {len(self.memory)}\nlast message -> role: {self.memory[i]['role']}, content -> {self.memory[message]['content']} \n",
                        f"{str(message) if not isinstance(message, str) else message}\n",
                    ]
                )
        return "done"


qs = [
    # "What are the best ways to treat PCOS symptoms besides birth control?",
    # "globally, what are some of the best cities and/or regions for lesbian US expats right now?",
    "what tech skills are most going to continue being extremely hireable as AI improves?",
    "which companies look best positioned to grow over the next 5 years in technology and are worth seeking employment at for junior/mid-level software engineers?"
    "What are some low-overhead side-business ideas for a busy grad student looking to generate passive income?",
]


async def main():
    orchestrator = ResearchOrchestrator()
    result = await orchestrator.execute_research(qs[random.randint(0, len(qs) - 1)])
    if result:
        with open("output.txt", "w") as f:
            for entry in result:
                # if entry == "final_response":
                #     if isinstance(entry, (dict, object, json)):
                #         d = json.loads(result[entry])
                #         for k in d:
                #             if k == "subtask_id" or k == "status":
                #                 f.write(f"{k}:{d[k]}\n")
                if entry == "tool_calls_count":
                    f.write(f"Tool Calls Count: {result[entry]}\n")
                if entry == "error":
                    f.write(f"Error Message: {result[entry]}\n")
                if entry == "conversation":
                    for item in result[entry]:
                        f.writelines(
                            [
                                f"conversation length: {len(result[entry])}\nlast message -> role: {result[entry][-1]['role']}, content -> {result[entry][-1]['content']} \n",
                                f"{str(item) if not isinstance(item, str) else item}\n",
                            ]
                        )

        # pretty(result["final_response"])
        return result


if __name__ == "__main__":
    asyncio.run(main())


# Using all of the outputs from subagents ran, write a long, thorough, and comprehensive report packed with specific examples and real world evidence that fully addresses the user query. This report should read like a research essay, not just a bulletted summary of the findings.
