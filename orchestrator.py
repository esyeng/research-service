import datetime
from typing import List
from helpers.llmclient import llm_call, extract_json_from_markdown
from utils.types import (
    SubTask,
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

    MAX_SUBAGENTS = 4
    MAX_SEARCHES_PER_AGENT = 10
    SUBAGENT_TIMEOUT = 120

    def __init__(self):
        self.memory = []

    def _allocate_resources(
        self, task_plan: TaskPlan, orchestrate: bool = False
    ) -> ResourceConfig | str:
        model_choices = {
            "straightforward": "claude-3-5-haiku-20241022",
            "moderate": "claude-sonnet-4-20250514",
            "complex": "claude-opus-4-1-20250805",
        }
        simp = task_plan.complexity_score == 1
        mid = task_plan.complexity_score == 2
        if orchestrate:
            model_choices["complex"]
        if task_plan.complexity_score > 3:
            raise OrchestratorError("Complexity score out of range")

        return ResourceConfig(
            max_subagents=1 if simp else 3 if mid else 4,
            searches_per_agent=4 if simp else 7 if mid else 12,
            model_per_task=(
                model_choices["straightforward"] if simp else model_choices["moderate"]
            ),
            total_token_budget=8000 if simp else 16000,
            timeout_seconds=60 if simp else 120,
        )

    def _build_task_plan(self, **kwargs) -> str:
        """
        Construct the LLM prompt for a given query.
        Encapsulates the template, instructions, and examples.
        """
        # TODO - Determine next step in iterative building:
        # either
        # modularize then chunk analysis, allocation, delegation, monitoring, synthesis
        # orchestrate using tools from master prompt
        # I think MVP -> modular then stitch
        # possibly improve efficiency -> master prompt with tooling
        template = """
    Purpose: Transform user query into actionable research plan
    You are an AI research assistant working as a key analyst in a research workflow that handles research queries and evaluates their complexity in order to plan research sub-tasks which will be delegated to sub-agents.
    The current date is {current_date}
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
    # next step here: run allocate_resources on 
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required prompt variable: {e}")

    def _build_subagent_prompt(self, subtask: SubTask, tools_available: List[str]) -> str:
        """Build focused subagent prompt using Anthropic's template"""
    
        # Adapt the complexity to tool call budget
        complexity_to_budget = {
            1: "under 5 tool calls",  # simple
            2: "5-8 tool calls",      # medium  
            3: "8-15 tool calls"      # complex
        }
        
        # This is Anthropic's prompt with your task injected
        return f"""
        You are a research subagent working as part of a team. The current date is {datetime}. 

        <task>
        Objective: {subtask.objective}
        Expected Output: {subtask.expected_output}
        Suggested Starting Points: {subtask.search_focus}
        Research Budget: {complexity_to_budget.get(self._estimate_subtask_complexity(subtask), "5-8 tool calls")}
        Maximum Tool Calls: {subtask.max_search_calls}
        </task>

            {research_subagent_prompt}  # The full prompt you provided

        Available tools: {", ".join(tools_available)}
        """

    def _estimate_subtask_complexity(self, subtask: SubTask) -> int:
        """Quick heuristic to estimate subtask complexity for budget setting"""
        # Simple heuristics based on objective length, search focus count, etc.
        if len(subtask.search_focus) <= 2 and len(subtask.objective.split()) <= 10:
            return 1
        elif len(subtask.search_focus) <= 4 and len(subtask.objective.split()) <= 20:
            return 2
        else:
            return 3

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
        plan_json = self._build_task_plan(query=query, current_date=datetime.date.today())
        raw = llm_call(query, plan_json)
        return self._parse_and_validate(raw)
        
    
    async def execute_research(self, query: str) -> dict:
        """Main research flow with orchestrated tool-calling"""
        task_plan = self.analyze_query(query)
        orchestration_prompt = f"""
        You are a research orchestrator executing this plan:

        Original Query: {query}
        Strategy: {task_plan.strategy}
        Query Type: {task_plan.query_type}
        Subtasks: {len(task_plan.subtasks)} parallel tasks

        Your job:
        1. Use run_subagent tool for each subtask in parallel
        2. Monitor progress and handle any failures
        3. Synthesize all results into a comprehensive report
        4. Use complete_research when done

        Key constraints from planning:
        - Maximum {len(task_plan.subtasks)} subagents
        - Each subtask has specific boundaries to prevent overlap
        - Stop research when you have sufficient information

        Execute the plan now using parallel subagent calls.
        """
        


def main():
    orchestrator = ResearchOrchestrator()
    return orchestrator.analyze_query("What are the best ways to treat PCOS symptoms besides birth control?")


if __name__ == "__main__":
    main()
