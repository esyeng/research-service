import pytest
import json
from orchestrator import ResearchOrchestrator
from utils.types import (
    OrchestratorError,
    TaskDecompositionError,
    SubagentTimeoutError,
    SynthesisError,
)

# --- test doubles / fixtures ---


@pytest.fixture(autouse=True)
def patch_llm_call(monkeypatch):
    """
    Automatically patch llm_call in orchestrator to avoid real API hits.
    You can override behavior per test by reassigning patch_llm_call.side_effect.
    """
    responses = {}

    def fake_llm_call(query: str, prompt: str):
        response = responses.get(query)
        if response is None:
            return None
        # convert dict to JSON string
        return json.dumps(response)

    monkeypatch.setattr("orchestrator.llm_call", fake_llm_call)
    return responses


# --- actual tests ---


@pytest.mark.asyncio
async def test_simple_query_decomposition(patch_llm_call):
    """Single fact queries should return 1 straightforward subtask"""
    orchestrator = ResearchOrchestrator()
    patch_llm_call["What is the population of Tokyo?"] = {
        "query_type": "straightforward",
        "complexity": 1,
        "strategy": "Direct fact-finding",
        "subtasks": [
            {
                "id": "task_001",
                "objective": "Find Tokyo population",
                "scope": "Latest UN or gov data only",
                "search_queries": ["Tokyo population 2025"],
                "expected_output": "Current population figure",
                "max_searches": 2,
                "priority": "high",
            }
        ],
    }

    result = await orchestrator.analyze_query("What is the population of Tokyo?")
    assert result.query_type == "straightforward"
    assert result.complexity_score == 1
    assert len(result.subtasks) == 1


@pytest.mark.asyncio
async def test_comparative_query_decomposition(patch_llm_call):
    """Comparative queries should yield 2-3 subtasks (breadth_first)"""
    orchestrator = ResearchOrchestrator()
    patch_llm_call["Compare the economies of Nordic countries"] = {
        "query_type": "breadth_first",
        "complexity": 2,
        "strategy": "Split by country",
        "subtasks": [
            {
                "id": "task_001",
                "objective": "Denmark economy",
                "scope": "Denmark only",
                "search_queries": ["Denmark economy 2025"],
                "expected_output": "GDP, inflation, key sectors",
                "max_searches": 5,
                "priority": "high",
            },
            {
                "id": "task_002",
                "objective": "Norway economy",
                "scope": "Norway only",
                "search_queries": ["Norway economy 2025"],
                "expected_output": "GDP, inflation, key sectors",
                "max_searches": 5,
                "priority": "high",
            },
        ],
    }

    result = await orchestrator.analyze_query(
        "Compare the economies of Nordic countries"
    )
    assert result.query_type == "breadth_first"
    assert 2 <= len(result.subtasks) <= 4


@pytest.mark.asyncio
async def test_depth_query_decomposition(patch_llm_call):
    """Depth-first queries should produce multiple perspectives on one topic"""
    orchestrator = ResearchOrchestrator()
    patch_llm_call["Best approach to AI finance agents in 2025?"] = {
        "query_type": "depth_first",
        "complexity": 3,
        "strategy": "Analyze from technical, regulatory, and market perspectives",
        "subtasks": [
            {
                "id": "task_001",
                "objective": "Tech methods",
                "scope": "Architecture + models",
                "search_queries": ["AI finance agent architecture"],
                "expected_output": "Comparison of approaches",
                "max_searches": 5,
                "priority": "high",
            },
            {
                "id": "task_002",
                "objective": "Regulatory",
                "scope": "US/EU compliance",
                "search_queries": ["AI finance regulation 2025"],
                "expected_output": "Legal constraints",
                "max_searches": 5,
                "priority": "medium",
            },
            {
                "id": "task_003",
                "objective": "Market adoption",
                "scope": "Industry adoption",
                "search_queries": ["AI finance adoption trends"],
                "expected_output": "Adoption case studies",
                "max_searches": 5,
                "priority": "medium",
            },
        ],
    }

    result = await orchestrator.analyze_query(
        "Best approach to AI finance agents in 2025?"
    )
    assert result.query_type == "depth_first"
    assert result.complexity_score == 3
    assert 2 <= len(result.subtasks) <= 4


@pytest.mark.asyncio
async def test_overly_broad_query_caps_subtasks(patch_llm_call):
    """Even if LLM wants to return 10 subtasks, orchestrator should cap at 4"""
    orchestrator = ResearchOrchestrator()
    # simulate ridiculous LLM output
    patch_llm_call["Explain history of the universe"] = {
        "query_type": "breadth_first",
        "complexity": 3,
        "strategy": "Split by epochs",
        "subtasks": [
            {
                "id": f"task_{i:03}",
                "objective": f"Epoch {i}",
                "scope": "wide",
                "search_queries": ["big query"],
                "expected_output": "stuff",
                "max_searches": 5,
                "priority": "low",
            }
            for i in range(10)
        ],
    }

    result = await orchestrator.analyze_query("Explain history of the universe")
    # TODO enforce truncation inside analyze_query
    assert len(result.subtasks) <= 4


@pytest.mark.asyncio
async def test_invalid_json_raises_decomposition_error(monkeypatch):
    """If invalid JSON and/or incorrect nonsense, raise TaskDecompositionError"""

    orchestrator = ResearchOrchestrator()

    def fake_llm_call(query, prompt):
        return "this is not JSON"

    monkeypatch.setattr("orchestrator.llm_call", fake_llm_call)

    with pytest.raises(TaskDecompositionError):
        await orchestrator.analyze_query("nonsense query")


@pytest.mark.asyncio
async def test_missing_fields_in_response(monkeypatch):
    """If required fields are missing, raise TaskDecompositionError"""

    orchestrator = ResearchOrchestrator()

    def fake_llm_call(query, prompt):
        return {
            "query_type": "straightforward",
            "complexity": 1,
            "strategy": "Something vague",
        }

    monkeypatch.setattr("orchestrator.llm_call", fake_llm_call)

    with pytest.raises(TaskDecompositionError):
        await orchestrator.analyze_query("incomplete plan query")


@pytest.mark.asyncio
async def test_too_many_subtasks_triggers_error(monkeypatch):
    """If over max subagent capacity, raise TaskDecompositionError"""

    orchestrator = ResearchOrchestrator()

    def fake_llm_call(query, prompt):
        return {
            "query_type": "breadth_first",
            "complexity": 3,
            "strategy": "Make everything its own subtask",
            "subtasks": [
                {
                    "id": f"task_{i}",
                    "objective": "blah",
                    "scope": "meh",
                    "search_queries": ["q"],
                    "expected_output": "x",
                    "max_searches": 1,
                    "priority": "low",
                }
                for i in range(10)
            ],
        }

    monkeypatch.setattr("orchestrator.llm_call", fake_llm_call)

    with pytest.raises(TaskDecompositionError):
        await orchestrator.analyze_query("way too broad query")


# **Test Cases:**
# - Simple factual query → 1-2 subtasks
# - Comparative analysis → 2-3 subtasks
# - Comprehensive research → 3-4 subtasks
# - Edge case: Overly broad query → Should cap at 4 subtasks
