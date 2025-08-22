import pytest
import json
from orchestrator import ResearchOrchestrator
from utils.types import (
    TaskPlan,
    SubTask,
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


def test_simple_query_decomposition(patch_llm_call):
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

    result = orchestrator.analyze_query("What is the population of Tokyo?")
    assert result.query_type == "straightforward"
    assert result.complexity_score == 1
    assert len(result.subtasks) == 1


def test_comparative_query_decomposition(patch_llm_call):
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

    result = orchestrator.analyze_query("Compare the economies of Nordic countries")
    assert result.query_type == "breadth_first"
    assert 2 <= len(result.subtasks) <= 4


def test_depth_query_decomposition(patch_llm_call):
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

    result = orchestrator.analyze_query("Best approach to AI finance agents in 2025?")
    assert result.query_type == "depth_first"
    assert result.complexity_score == 3
    assert 2 <= len(result.subtasks) <= 4


def test_overly_broad_query_caps_subtasks(patch_llm_call):
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

    result = orchestrator.analyze_query("Explain history of the universe")
    # TODO enforce truncation inside analyze_query
    assert len(result.subtasks) <= 4


def test_invalid_json_raises_decomposition_error(monkeypatch):
    """If invalid JSON and/or incorrect nonsense, raise TaskDecompositionError"""

    orchestrator = ResearchOrchestrator()

    def fake_llm_call(query, prompt):
        return "this is not JSON"

    monkeypatch.setattr("orchestrator.llm_call", fake_llm_call)

    with pytest.raises(TaskDecompositionError):
        orchestrator.analyze_query("nonsense query")


def test_missing_fields_in_response(monkeypatch):
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
        orchestrator.analyze_query("incomplete plan query")


def test_resource_allocation():
    """Ensure orchestrator._allocate_resources() delegates"""
    plan = TaskPlan(
        strategy="Break down PCOS treatment into distinct therapeutic categories since PCOS has multiple symptom clusters (metabolic, reproductive, cosmetic) that can be addressed through different non-hormonal approaches",
        query_type="breadth_first",
        subtasks=[
                SubTask(
                    id="task_001",
                    objective="Research dietary and nutritional interventions for PCOS management",
                    search_focus=[
                        "PCOS diet treatment insulin resistance",
                        "anti-inflammatory diet PCOS",
                        "inositol PCOS treatment",
                        "low glycemic diet PCOS",
                        "PCOS nutritional supplements evidence"
                    ],
                    expected_output="Comprehensive overview of dietary modifications, specific eating patterns, and nutritional supplements with evidence for PCOS symptom improvement",
                    max_search_calls=5
                    
                )
                {
                    "id": "task_001",
                    "objective": "Research dietary and nutritional interventions for PCOS management",
                    "scope": "Focus on evidence-based dietary approaches, supplements, and nutritional strategies that help manage insulin resistance, weight, and hormonal balance in PCOS patients",
                    "search_queries": [
                        "PCOS diet treatment insulin resistance",
                        "anti-inflammatory diet PCOS",
                        "inositol PCOS treatment",
                        "low glycemic diet PCOS",
                        "PCOS nutritional supplements evidence"
                    ],
                    "expected_output": "Comprehensive overview of dietary modifications, specific eating patterns, and nutritional supplements with evidence for PCOS symptom improvement",
                    "max_searches": 5,
                    "priority": "high"
                },
                {
                    "id": "task_002",
                    "objective": "Investigate lifestyle modifications and exercise interventions for PCOS",
                    "scope": "Research physical activity recommendations, stress management techniques, sleep optimization, and other lifestyle changes that improve PCOS symptoms without medication",
                    "search_queries": [
                        "PCOS exercise treatment recommendations",
                        "resistance training PCOS benefits",
                        "stress management PCOS",
                        "sleep PCOS symptoms",
                        "lifestyle interventions PCOS clinical trials"
                    ],
                    "expected_output": "Evidence-based lifestyle modification strategies including specific exercise protocols, stress reduction techniques, and sleep hygiene practices for PCOS management",
                    "max_searches": 5,
                    "priority": "high"
                },
                {
                    "id": "task_003",
                    "objective": "Research alternative and complementary medicine approaches for PCOS",
                    "scope": "Explore non-pharmaceutical treatments including herbal remedies, acupuncture, mind-body therapies, and other integrative medicine approaches with scientific backing",
                    "search_queries": [
                        "herbal treatments PCOS spearmint cinnamon",
                        "acupuncture PCOS treatment studies",
                        "yoga meditation PCOS benefits",
                        "traditional medicine PCOS",
                        "integrative PCOS treatment approaches"
                    ],
                    "expected_output": "Overview of complementary and alternative treatments with evidence for efficacy, safety considerations, and integration with conventional care",
                    "max_searches": 5,
                    "priority": "medium"
                },
                {
                    "id": "task_004",
                    "objective": "Examine medical treatments and procedures for PCOS beyond hormonal contraceptives",
                    "scope": "Research non-hormonal medications, medical procedures, and other clinical interventions used to treat specific PCOS symptoms like hirsutism, acne, and metabolic dysfunction",
                    "search_queries": [
                        "metformin PCOS treatment non-diabetic",
                        "spironolactone PCOS hirsutism",
                        "laser hair removal PCOS",
                        "bariatric surgery PCOS",
                        "non-hormonal PCOS medications"
                    ],
                    "expected_output": "Medical treatment options including medications, procedures, and clinical interventions that don't involve hormonal birth control, with efficacy and safety profiles",
                    "max_searches": 5,
                    "priority": "high"
                }
            ]
    )


"""
Complexity 1 → 1 agent, 3-5 searches, haiku
Complexity 2 → 2-3 agents, 5-10 searches, sonnet
Complexity 3 → 3-4 agents, 10-15 searches, sonnet
"""

# **Test Cases:**
# - Simple factual query → 1-2 subtasks
# - Comparative analysis → 2-3 subtasks
# - Comprehensive research → 3-4 subtasks
# - Edge case: Overly broad query → Should cap at 4 subtasks
