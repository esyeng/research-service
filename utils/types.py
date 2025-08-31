from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, TypedDict, Union

# Data classes ******************************


@dataclass
class ToolCall:
    id: str
    type: str
    name: str
    input: Union[str, Dict[str, Any], object]


@dataclass
class SubTask:
    id: str
    objective: str
    search_focus: List[str]
    expected_output: str
    priority: str
    max_search_calls: int = 1


@dataclass
class TaskPlan:
    strategy: str
    query_type: str
    subtasks: List[SubTask] = field(default_factory=list)
    complexity_score: int = 1


@dataclass
class ResourceConfig:
    max_subagents: int
    searches_per_agent: int
    model_per_task: str = "claude-sonnet-4-20250514"
    total_token_budget: int = 16000
    timeout_seconds: int = 120


@dataclass
class SubTaskResult(TypedDict):
    task_complete: bool
    insights: str
    findings: List[str]
    sources: List[str]
    confidence: float


class Query(Enum):
    straightforward = 1
    breadth_first = 2
    depth_first = 3


# Error handling ****************************


class OrchestratorError(Exception):
    """Base exception for orchestrator failures"""

    def __init__(
        self, message: str, task_id: str | None = None, cause: Exception | None = None
    ):
        self.task_id = task_id
        self.cause = cause
        self.message = message
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [self.message]
        if self.task_id:
            parts.append(f"(task_id={self.task_id})")
        if self.cause:
            parts.append(f"caused by {type(self.cause).__name__}: {self.cause}")
        return " | ".join(parts)

    def __str__(self) -> str:
        return self._format_message()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self._format_message()}>"


class TaskDecompositionError(OrchestratorError):
    """Failed to break down query into subtasks"""


class SubagentTimeoutError(OrchestratorError):
    """Subagent exceeded time limit"""

    def __init__(self, task_id: str, timeout: float, cause: Exception | None = None):
        self.timeout = timeout
        msg = f"Subagent timed out after {timeout:.2f}s"
        super().__init__(msg, task_id=task_id, cause=cause)


class SynthesisError(OrchestratorError):
    """Failed to combine results into coherent report"""
