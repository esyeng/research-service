import json
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import List

from helpers.llmclient import llm_call, extract_json_from_markdown
from utils.types import OrchestratorError, TaskDecompositionError


@dataclass
class SubTask:
    id: str
    objective: str
    search_focus: List[str]
    expected_output: str
    max_search_calls: int = 1


@dataclass
class TaskPlan:
    strategy: str
    query_type: str
    subtasks: List[SubTask] = field(default_factory=list)
    complexity_score: int = 1  # scale: 1=simple, 2=moderate, 3=complex


class Query(Enum):
    straightforward = 1
    breadth_first = 2
    depth_first = 3


class ResearchOrchestrator:
    MAX_SUBAGENTS = 4
    MAX_SEARCHES_PER_AGENT = 10
    SUBAGENT_TIMEOUT = 120

    def __init__(self):
        self.memory = []

    def _build_prompt(self, query: str) -> str:
        """
        Construct the LLM prompt for a given query.
        Encapsulates the template, instructions, and examples.
        """
        template = """
    Purpose: Transform user query into actionable research plan
    You are an AI research assistant working as a key analyst in a research workflow that handles research queries and evaluates their complexity in order to plan research sub-tasks which will be delegated to sub-agents.

    Query to analyze:
    "{query}"

    Instructions:
    - Categorize query type: straightforward, breadth_first, depth_first
    - Assign complexity score (1-3)
    - Generate subtasks (1-4) with clear boundaries, max searches, expected outputs
    - Ensure zero overlap between subtask scopes

    query types with explanation (enum values) ->
    1. straightforward: the problem is focused, well-defined, and can be effectively answered by a single focused investigation or fetching a single resource from the internet.\n
    2. breadth_first: the problem can be broken into distinct, independent sub-questions, and calls for "going wide" by gathering information about each sub-question.\n
    3. depth_first: the problem requires multiple perspectives on the same issue, and calls for "going deep" by analyzing a single topic from many angles.
        
    Examples:
    - straightforward: "What is the population of Tokyo?"
    - breadth_first: "Compare the economic systems of three Nordic countries"
    - depth_first: "Analyze AI finance agent design approaches in 2025"
    

    * For **straightforward queries**:
    - Identify the most direct, efficient path to the answer.
    - Determine whether basic fact-finding or minor analysis is needed.
    - Specify exact data points or information required to answer.
    - Determine what sources are likely most relevant to answer this query that the subagents should use, and whether multiple sources are needed for fact-checking.
    - Plan basic verification methods to ensure the accuracy of the answer.
    - Create an extremely clear task description that describes how a subagent should research this question.

    * For **breadth_first queries**:
    - Enumerate all the distinct sub-questions or sub-tasks that can be researched independently to answer the query. 
    - Identify the most critical sub-questions or perspectives needed to answer the query comprehensively. Only create additional sub-tasks if the query has clearly distinct components that cannot be efficiently handled by fewer sub-agents
    - Prioritize these sub-tasks based on their importance and expected research complexity.
    - Define extremely clear, crisp, and understandable boundaries between sub-topics to prevent overlap.
    - Plan how findings will be aggregated into a coherent whole.

    * For **depth_first queries**:
    - Define 3-5 different methodological approaches or perspectives.
    - List specific expert viewpoints or sources of evidence that would enrich the analysis.
    - Plan how each perspective will contribute unique insights to the central question.
    - Specify how findings from different approaches will be synthesized.

    <delegation_format>
    Output your plan as JSON:
    {{
        "query_type": "straightforward|breadth_first|depth_first",
        "complexity": 1-3,
        "strategy": "Brief explanation of approach",
        "subtasks": [
            {{
                "id": "task_001",
                "objective": "Specific research goal",
                "scope": "Clear boundaries of what to research",
                "search_queries": ["suggested", "search", "terms"],
                "expected_output": "What success looks like",
                "max_searches": 5,
                "priority": "high|medium|low"
            }}
        ]
    }}
    </delegation_format>
    """
        return template.format(query=query)

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
        prompt = self._build_prompt(query)
        raw = llm_call(query, prompt)
        return self._parse_and_validate(raw)


def main():
    orchestrator = ResearchOrchestrator()
    return orchestrator.analyze_query("What is the capital of Fiji?")


if __name__ == "__main__":
    main()
