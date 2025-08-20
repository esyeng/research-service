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
