## Multi-Agent Research System - Minimum Implementation Requirements

*Initial commit* ->
- Added orchestrator.py to handle research queries and generate task plans.
- Introduced TaskPlan and SubTask data classes for structured task management.
- Developed a prompt-building method for LLM interaction to analyze queries.
- Implemented JSON parsing and validation for LLM responses, raising errors for invalid structures.
- Created research_lead.py and research_subagent.py prompts for guiding research processes.
- Established a requirements.txt file for necessary dependencies.
- Added unit tests for the ResearchOrchestrator to validate query decomposition and error handling.
- Included utility types for error management in types.py.
- Added example output JSON for reference in research tasks.


### Core Architecture Requirements

**System Components:**
1. **Lead Orchestrator Agent** - Claude Opus/Sonnet for strategy & coordination
2. **Research Subagents** (2-5 parallel workers) - Claude Haiku/Sonnet for cost efficiency
3. **Memory Store** - External persistence for context management
4. **Tool Integration Layer** - Web search, document retrieval, citation handling
5. **Coordination Engine** - Task delegation & result synthesis

### Essential Features (MVP)

**1. Task Decomposition Engine**
- Input: User research query
- Output: 2-5 discrete subtasks with clear boundaries
- Each subtask must specify: objective, output format, tools allowed, success criteria

**2. Parallel Execution Framework**
- Spawn 2-5 subagents simultaneously (start conservative)
- Each subagent gets clean context + specific task
- Timeout handling (30-120s per subtask)
- Result collection & error handling

**3. Memory Management**
- Store orchestrator strategy in external memory
- Context summarization when approaching token limits
- Clean handoffs between agent generations

**4. Tool Integration**
- Web search API (Brave/Perplexity)
- Document parsing capability
- Basic citation extraction
- **Scaling rules embedded in prompts:** Simple queries (1 agent, 3-10 calls), Complex research (3-5+ agents, 10-15 calls each)

### Technical Specifications

**Resource Management:**
-

- Model allocation: Opus for orchestrator, Sonnet for workers
- Parallel tool calling at both orchestrator and subagent levels

**Prompt Engineering Requirements:**
-

- Embed OODA loop logic in subagent prompts (observe, orient, decide, act)
- Include explicit resource allocation guidelines

**Error Handling:**
- Subagent failure recovery (retry with refined instructions)
- Tool failure fallbacks
- Context overflow management
- Early termination conditions

### Implementation Priorities

**Phase 1 (Week 1-2): Core Loop**
1. Basic orchestrator → single subagent → synthesis
2. Memory store integration
3. Simple web search tool
4. Manual scaling (fixed 2-3 subagents)

**Phase 2 (Week 3): Parallelization**
1. Multi-subagent spawning
2. Result coordination
3. Dynamic scaling based on query complexity
4. Basic evaluation framework

**Phase 3 (Week 4+): Production Features**
1. Advanced tool integration
2. Citation agent
3. Evaluation & monitoring
4. Performance optimization

### Success Metrics

**Functional Requirements:**
- Handle breadth-first queries (e.g., "Find all board members of Tech S&P 500 companies")
- 90%+ task completion rate on research queries
- Proper citation attribution
- Sub-5-minute response time for complex queries

**Performance Targets:**

- Token efficiency monitoring
- Quality evaluation via LLM-as-judge + human spot checks

### Technology Stack Recommendations

**Orchestration:** Python + asyncio for parallel execution
**Memory:** Redis/PostgreSQL for session persistence  
**Tools:** Brave Search API, BeautifulSoup, PDF parsers
**Models:** Anthropic Claude API (tier mix based on role)
**Monitoring:** Basic logging + token usage tracking

### Risk Mitigation

**Known Failure Modes:**

- Solution: Strict resource limits + detailed task specifications

**Development Approach:**

- Build evaluation framework early
- Monitor token consumption religiously

## ResearchOrchestrator - High-Level Specification

**User Story**

As a research engineer:

I want an orchestrator that safely decomposes queries and manages parallel subagents
So that I can conduct comprehensive research more effectively than a single agent
Core Class Requirements

### 1. Query Analysis & Planning
*Method*: `analyze_query(query: str) -> TaskPlan`
*Purpose*: Transform user query into actionable research plan
*Required Behavior*:
    Categorize query type (straightforward/breadth-first/depth-first)
    Generate 1-4 subtasks based on complexity
    Assign complexity score (1-3)
    Ensure zero overlap between subtask scopes
    Set appropriate resource limits per subtask

**Passing Criteria**:

✅ "What is the GDP of Japan?" → 1 subtask
✅ "Compare tax systems of Nordic countries" → 3-4 subtasks (one per country)
✅ "Analyze causes of 2008 crisis" → 3-4 subtasks (different perspectives)
✅ Subtasks have mutually exclusive scopes
✅ Combined subtasks fully address original query
❌ Never exceeds 4 subtasks (hard limit)
❌ Rejects harmful research requests

**Required Variables**:

Query type enum
Subtask list with clear boundaries
Resource allocation per task
Priority ordering

### 2. Resource Allocation
*Method*: `allocate_resources(complexity_score: int) -> ResourceConfig`
*Purpose*: Enforce Anthropic's scaling rules to prevent token explosion
*Required Behavior*:
    Map complexity to agent count and search limits
    Select appropriate model tier
    Set token budgets
    Define timeout windows

**Passing Criteria**:

✅ Complexity 1 → 1 agent, 3-5 searches, Haiku model
✅ Complexity 2 → 2-3 agents, 5-10 searches, Haiku model
✅ Complexity 3 → 3-4 agents, 10-15 searches, Sonnet for synthesis
✅ Total token budget never exceeds defined maximum
✅ Timeout scales with complexity

### 3. Subtask Delegation
*Method*: `delegate_subtasks(subtasks: List[SubTask]) -> List[Future]`
*Purpose*: Launch parallel subagents with isolated contexts
*Required Behavior*:
    Create async tasks for each subtask
    Provide clean, isolated context to each subagent
    Include task-specific instructions and constraints
    Launch all subagents within 1 second (true parallelism)
    Return futures for monitoring

**Passing Criteria**:

✅ All subagents start simultaneously (not sequential)
✅ Each subagent has only its specific task context
✅ No shared state between subagents
✅ Futures can be cancelled if needed
✅ Memory checkpoint created before launch

*Helper Functions Needed*:

`_create_subagent_context(subtask)` - Isolate context
`_format_subagent_prompt(subtask)` - Generate focused instructions
`_validate_subtask_boundaries(subtasks)` - Ensure no overlap

### 4. Execution Monitoring
*Method*: `monitor_execution(futures: List[Future]) -> List[SubTaskResult]`
*Purpose*: Track parallel execution and handle failures gracefully
*Required Behavior*:
    Wait for completion with timeout
    Handle partial failures without stopping others
    Cancel overtime subagents
    Collect results in order
    Track token usage per subagent

**Passing Criteria**:

✅ Successful agents return results even if others fail
✅ Timeout (120s) cancels pending tasks
✅ Failed agents return error status, not exceptions
✅ At least one result always returned (no total failure)
✅ Token usage logged per subagent

### 5. Result Synthesis
*Method*:  `synthesize_results(query, task_plan, results) -> ResearchReport`
*Purpose*: Combine findings into coherent report
*Required Behavior*:
    Deduplicate overlapping findings
    Resolve conflicting information
    Identify information gaps
    Generate structured report
    Calculate confidence score

**Passing Criteria**:

✅ Handles complete results (all agents succeed)
✅ Handles partial results (some agents fail)
✅ Deduplicates identical findings
✅ Flags conflicts for user attention
✅ Lists gaps as "unable to determine"
✅ Confidence score reflects result completeness
❌ Never crashes on empty results

*Helper Functions Needed*:

`_deduplicate_findings(results)` - Remove redundant info
`_resolve_conflicts(findings)` - Handle contradictions`
`_identify_gaps(plan, results)` - Find missing info
`_calculate_confidence(results)` - Score reliability

### 6. State Management
*Methods*:

`checkpoint_state(stage: str, data: dict) -> None`
`recover_from_checkpoint(session_id: str) -> Optional[dict]`

*Purpose*: Enable recovery from failures
*Required Behavior*:
    Save state at key stages (plan/delegation/results/synthesis)
    Include session identifier
    Store in persistent memory
    Enable mid-execution recovery
    Clean up old checkpoints

**Passing Criteria**:

✅ Checkpoint after query analysis
✅ Checkpoint before subagent launch
✅ Checkpoint after result collection
✅ Can resume from any checkpoint
✅ Old sessions auto-expire

### Safety Requirements
**Token Management**
*Class Variable*: MAX_TOTAL_TOKENS = 50000
*Required Behavior*:
    Track cumulative usage
    Stop before exceeding limit
    Log warning at 80% usage
    Return partial results if limit reached

**Subagent Limits**
*Class Constants*:
    `MAX_SUBAGENTS = 4`
    `MAX_SEARCHES_PER_AGENT = 10  `
    `SUBAGENT_TIMEOUT = 120`
*Required Behavior*:
    Hard stop at limits
    No configuration override
    Log attempts to exceed

**Error Handling**
*Required Exception Classes*:

`TaskDecompositionError` - Failed to break down query
`SubagentTimeoutError` - Agent exceeded time limit
`SynthesisError` - Cannot combine results
`SafetyViolationError` - Harmful query detected
`ResourceLimitError` - Token/search limit exceeded

**Testing Requirements**
*Unit Tests Required*:

    Query decomposition for all three types
    Resource allocation scaling
    Parallel execution verification
    Timeout handling
    Partial failure recovery
    Deduplication logic
    Conflict resolution
    Gap identification
    Safety limit enforcement
    Checkpoint/recovery cycle

*Integration Tests Required*:

    End-to-end simple query
    End-to-end complex query
    Multi-agent coordination
    Token limit compliance
    Error cascade handling

*Performance Criteria*

    Simple queries: < 30 seconds total
    Complex queries: < 120 seconds total
    Parallel launch: < 1 second
    Memory usage: < 500MB per session
    Token efficiency: < 15x single agent baseline

**Monitoring Requirements**
*Required Metrics*:

    Token usage per subagent
    Execution time per stage
    Success/failure rates
    Search counts per agent
    Confidence scores distribution

*Required Logs*:

    Query analysis decisions
    Resource allocation choices
    Subagent launch events
    Result synthesis reasoning
    Safety limit triggers




