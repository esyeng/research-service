import datetime
import asyncio
import random
import json
from helpers.llmclient import LLMClient
from helpers.tools import web_fetch
from helpers.data_methods import plan, extract_json_from_markdown
from utils.types import SubTask, TaskPlan, TaskDecompositionError
from newspaper import Article
from helpers.agent import SearchBot


class ResearchOrchestrator:
    """Orchestrates the decomposition and allocation of research queries into actionable sub-tasks for AI research agents.
    Attributes:
        MAX_SUBAGENTS (int): Maximum number of sub-agents allowed per query.
        MAX_SEARCHES_PER_AGENT (int): Maximum number of searches each sub-agent can perform.
        SUBAGENT_TIMEOUT (int): Timeout in seconds for each sub-agent's task.
        memory (list): Internal memory for storing orchestrator state or history.
    """

    MAX_SUBAGENTS = 5
    MAX_SEARCHES_PER_AGENT = 10
    SUBAGENT_TIMEOUT = 120
    CONVERSATION_TIMEOUT = 600

    def __init__(self):
        self.memory = []
        self.client = LLMClient()

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
        required_fields = ["strategy", "complexity", "subtasks"]
        for f in required_fields:
            if f not in plan_dict:
                raise TaskDecompositionError(f"Missing required field '{f}' in plan")
        subtasks = []
        if len(plan_dict["subtasks"]) > self.MAX_SUBAGENTS:
            plan_dict["subtasks"] = plan_dict["subtasks"][: self.MAX_SUBAGENTS]
        for i, st in enumerate(plan_dict["subtasks"], start=1):
            if i > self.MAX_SUBAGENTS:
                break
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
        raw = self.client.stream_synchronous(query, plan_json)
        return self._parse_and_validate(raw)

    def get_article_text(self, url: str):
        article = Article(url)
        article.download()
        article.parse()
        return article.text

    async def execute_research(
        self,
        query: str,
    ) -> dict:
        """Main research flow with programatic tool-calling"""
        task_plan = self.analyze_query(query)
        agent_results = []
        articles = []
        sources = []
        for task in task_plan.subtasks:
            agent = SearchBot(task)
            try:
                res = await agent._execute()
            except Exception as e:
                print(f"[ERROR] subagent {task.id} crashed: {e}", flush=True)
                continue
            # print(f"ran SearchBot on task: {task.id}")
            # print(f"{'=' * 20}\nsubagent result: {res}\n")
            if not isinstance(res, dict):
                print(f"[WARN] unexpected subagent result type: {type(res)}. Skipping.")
                continue
            status = res.get("status", "error")
            if status != "completed":
                print(
                    f"[WARN] subagent {task.id} returned status={status}; error={res.get('error')!r}"
                )
                maybe = res.get("final_response")
                if maybe:
                    agent_results.append(maybe)
                continue
            final = res.get("final_response")
            if final is not None:
                agent_results.append(final)
            if isinstance(final, dict) and final.get("sources"):
                for url in final.get("sources", []):
                    if url not in sources:
                        sources.append(url)
            convo = res.get("raw_conversation") or res.get("conversation")
            if convo and isinstance(convo, list):
                try:
                    self.record_memories(convo)
                except Exception as e:
                    print(f"[WARN] record_memories failed: {e}")
        for url in list(sources):
            try:
                text = self.get_article_text(url)
            except Exception as e:
                print(f"[WARN] failed to fetch article {url}: {e}")
                text = ""
            articles.append({"link": url, "text": text})
        research_findings_serialized = json.dumps(
            agent_results, ensure_ascii=False, indent=2
        )
        orchestration_prompt = f"""
        You are tasked with writing a comprehensive essay based on a given query and research findings. Your goal is to provide a detailed, impartial, and informative response that addresses the query in depth. Follow these instructions carefully:

        First, review the following research findings:

        <research_findings>{research_findings_serialized}
        </research_findings>


        Now, carefully analyze the query:

        <query>
        {query}
        </query>

        Before writing your essay, consider the following:

        1. Identify the main topics and subtopics related to the query.
        2. Organize the research findings into relevant categories.
        3. Look for connections, patterns, or contradictions in the data.
        4. Determine the most important and relevant information to include.

        Structure your essay as follows:

        1. Introduction: Briefly introduce the topic and provide context for the query.
        2. Main body: Divide this section into relevant subsections, each addressing a key aspect of the query.
        3. Conclusion: Summarize the main points and provide a balanced overview of the findings.

        When writing your essay:

        1. Remain objective and impartial throughout.
        2. Use clear, concise language appropriate for an academic or professional audience.
        3. Provide specific examples, data, and quotes from the research findings to support your points.
        4. Address any conflicting information or perspectives found in the research.
        5. Ensure a logical flow of ideas between paragraphs and sections.
        6. Use transitional phrases to connect ideas and improve readability.

        if you would like to see any result's full article text, you can find the article's full text via __item__.text in <articles>{articles}</articles>

        Citations and references:
        from these sources: {sources}
        1. Use in-text citations whenever you reference information from the research findings.
        2. Format citations as [Source X], where X is the number of the source as listed in the research findings.
        3. If quoting directly, use quotation marks and include the source number.

        Output your essay within <essay> tags. After the essay, provide a list of all sources cited within <sources> tags.

        Important: DO NOT include points as bullets or numbered lists within the essay, the correct format is as if writing an academic paper. If you find yourself tempted to take shortcuts or use shorthand, remember that you are writing for completion and thoroughness.

        Remember to thoroughly address the query, providing a comprehensive and detailed response that synthesizes the information from the research findings.
        """
        result = await self.client.call_llm_with_tools(
            orchestration_prompt,
            system="You are an expert academic writer",
            tools=[],
            model="claude-3-7-sonnet-20250219",
            max_tokens=16000,
            timeout=600,
        )
        # claude-3-7-sonnet-20250219 | claude-sonnet-4-20250514 | claude-opus-4-1-20250805
        #
        #
        if not isinstance(result, dict):
            print("[ERROR] orchestrator returned non-dict response:", result)
            return {
                "status": "error",
                "final_response": None,
                "raw_conversation": [],
                "error": "orchestrator_returned_non_dict",
            }
        final_response = result.get("final_response") or result.get("response") or ""
        raw_conv = result.get("raw_conversation") or result.get("conversation") or []
        err = result.get("error")

        print("FINAL RAW CONVERSATION:", raw_conv)
        print("FINAL ERROR:", err)

        if raw_conv:
            try:
                self.record_memories(raw_conv)
            except Exception as e:
                print(f"[WARN] record_memories failed after orchestrator: {e}")
        return {
            "status": result.get("status", "completed" if final_response else "error"),
            "final_response": final_response,
            "raw_conversation": raw_conv,
            "error": err,
            "tool_calls_used": result.get(
                "tool_calls_count", result.get("tool_calls_used", 0)
            ),
        }

    def record_memories(self, conversation):
        """
        Append conversation messages to self.memory and append a small human-readable log file.
        conversation: list of message dicts, each message has 'role' and 'content' (content is usually a list of blocks).
        """
        if not conversation:
            return "no conversation"
        self.memory.extend(conversation)
        try:
            with open("output.txt", "a", encoding="utf-8") as f:
                f.write(
                    f"\n--- memory dump at {datetime.datetime.utcnow().isoformat()} ---\n"
                )
                f.write(f"total memory length: {len(self.memory)}\n")
                for i, message in enumerate(conversation, start=1):
                    role = message.get("role", "unknown")
                    content = message.get("content")
                    try:
                        content_preview = json.dumps(content, ensure_ascii=False)
                    except Exception:
                        content_preview = repr(content)
                    if len(content_preview) > 1000:
                        content_preview = content_preview[:1000] + " ...[truncated]"
                    f.write(f"{i}. role={role} content={content_preview}\n")
        except Exception as e:
            print(f"[WARN] Failed to write memory file: {e}")
        return "done"


qs = [
    # "What are the best ways to treat PCOS symptoms besides birth control?",
    # "which companies may be increasing hiring of software engineers going into 2026?",
    # "globally, what are some of the best cities and/or regions for lesbian US expats right now?",
    # "what tech skills are most going to continue being extremely hireable as AI improves?",
    # "which companies look best positioned to grow over the next 5 years in technology and are worth seeking employment at for junior/mid-level software engineers?"
    # "What are some low-overhead side-business ideas for a busy grad student looking to generate passive income?",
    # "How fast will AI replace econometric modelers?",
    "delicious new york style pizza sauce recipe historical approaches",
    # "do caterpillars notice humans and interact with them with curiosity?"
]


async def main():
    orchestrator = ResearchOrchestrator()
    result = await orchestrator.execute_research(qs[random.randint(0, len(qs) - 1)])
    if result:
        print(f"final_response in result from main: {result['final_response']}")
        return result


if __name__ == "__main__":
    asyncio.run(main())

"""
dummy_plan = {
    "query_type": "breadth_first",
    "complexity": 2,
    "strategy": "Break down into distinct research areas: tech giants expanding operations, emerging growth companies, industry sectors with digital transformation needs, and companies with recent funding/expansion announcements. Each subtask covers different company categories to ensure comprehensive coverage without overlap.",
    "subtasks": [
        {
            "id": "task_001",
            "objective": "Research major tech companies and established corporations announcing expansion plans or increased engineering hiring for 2026",
            "scope": "Focus on Fortune 500 tech companies, major cloud providers, established software companies, and large corporations with significant tech divisions that have made public statements about 2026 hiring plans",
            "search_queries": [
                "tech companies hiring software engineers 2026",
                "Fortune 500 engineering hiring plans 2026",
                "major tech companies expansion 2026",
                "cloud providers hiring software developers 2026",
            ],
            "expected_output": "List of 10-15 major established companies with specific hiring announcements, expansion plans, or growth initiatives requiring software engineers in 2026",
            "max_searches": 5,
            "priority": "high",
        },
        {
            "id": "task_002",
            "objective": "Identify high-growth startups and scale-ups that recently secured funding and are likely to increase software engineering hiring",
            "scope": "Focus on startups that raised Series B+ funding in 2024-2025, unicorn companies preparing for IPO, and fast-growing private companies in hot sectors like AI, fintech, healthtech",
            "search_queries": [
                "startups hiring software engineers 2026",
                "venture funding 2024 2025 engineering hiring",
                "unicorn companies hiring plans 2026",
                "Series B startups software developer jobs",
            ],
            "expected_output": "List of 10-12 high-growth startups and scale-ups with recent funding that indicates expansion and engineering team growth in 2026",
            "max_searches": 5,
            "priority": "high",
        },
        {
            "id": "task_003",
            "objective": "Research traditional industries undergoing digital transformation that will need more software engineering talent",
            "scope": "Focus on non-tech industries like healthcare, finance, manufacturing, retail, automotive that are investing heavily in digital initiatives and need software engineering talent",
            "search_queries": [
                "digital transformation hiring software engineers 2026",
                "healthcare companies software developer jobs",
                "financial services engineering hiring 2026",
                "manufacturing digital initiatives hiring",
            ],
            "expected_output": "List of 8-10 companies from traditional industries that are expanding their software engineering teams due to digital transformation initiatives",
            "max_searches": 4,
            "priority": "medium",
        },
        {
            "id": "task_004",
            "objective": "Identify companies in emerging technology sectors with high growth potential requiring software engineering talent",
            "scope": "Focus on companies in AI/ML, quantum computing, autonomous vehicles, renewable energy tech, space tech, and other cutting-edge sectors that are scaling up",
            "search_queries": [
                "AI companies hiring software engineers 2026",
                "quantum computing jobs software developers",
                "autonomous vehicle companies hiring",
                "cleantech software engineering jobs 2026",
            ],
            "expected_output": "List of 8-10 companies in emerging tech sectors that are likely to significantly increase software engineering hiring based on market trends and growth trajectories",
            "max_searches": 4,
            "priority": "medium",
        },
    ],
}


"""
