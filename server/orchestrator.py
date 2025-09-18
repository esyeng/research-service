import datetime
import asyncio
import json
import random
from helpers.llmclient import LLMClient
from helpers.tools import web_search, web_fetch
from helpers.data_methods import plan, essay_prompt, extract_json_from_markdown
from utils.types import SubTask, TaskPlan, TaskDecompositionError
from newspaper import Article
from typing import AsyncGenerator, Any, List, Dict, Callable


class ResearchOrchestrator:
    def __init__(self, max_subagents: int, prompt_method: Callable):
        self.client = LLMClient()
        self.MAX_SUBAGENTS = max_subagents
        self.prompt_method = prompt_method

    def analyze_query(
        self, query: str, number_subtasks_to_run: int, max_searches_per_task: int
    ) -> TaskPlan:
        """Analyze query and create research plan"""
        plan_json = plan(
            query=query,
            current_date=datetime.date.today(),
            number_subtasks_to_run=number_subtasks_to_run,
            max_searches_per_task=max_searches_per_task,
        )
        raw = self.client.generate_text(plan_json, "You are an expert research planner")
        return self._parse_and_validate(raw)

    async def analyze_query_stream(self, query: str):
        plan_json = plan(query=query, current_date=datetime.date.today())
        full_response = ""
        async for chunk in self.client.stream_text(
            plan_json, "You are an expert research planner"
        ):
            full_response += chunk
            yield chunk

    async def execute_research_sync(self, query: str, n_tasks: int, max_searches: int):
        """equential research execution that only returns final result"""
        final_essay = ""
        try:
            print("run synchronous researcher")
            task_plan = self.analyze_query(query, n_tasks, max_searches)
            if task_plan:
                print("task plan generated, executing tasks...")
            research_data = []
            sources = []

            for i, task in enumerate(task_plan.subtasks, 1):
                print(f"executing task {i}/{len(task_plan.subtasks)}: {task.objective}")
                task_result = await self._execute_research_task(task)
                research_data.append(task_result)
            if any(result.get("sources") for result in research_data):
                for result in research_data:
                    sources.append(*result.get("sources", []))
                print("research complete, writing essay...")
                essay = await self._generate_final_essay(research_data, query, sources)
                if essay:
                    final_essay = essay
            return final_essay
        except Exception as e:
            print(f"❌ Research failed: {str(e)}\n")

    async def execute_research(
        self, query: str, n_tasks: int, max_searches: int
    ) -> AsyncGenerator[str, None]:
        """Simplified sequential research execution that yields results as it runs"""
        final_essay = ""
        try:
            # 1. Announce start
            yield f"\n\n🔍 Starting research on: {query}\n\n"

            # 2. Create research plan
            yield "\n\n📋 Creating research plan...\n"
            task_plan = self.analyze_query(query, n_tasks, max_searches)
            if task_plan.strategy:
                yield f"\n\n💭 Strategy:\n --> {task_plan.strategy}\n\n"
            research_data = []

            # 3. Execute tasks sequentially
            for i, task in enumerate(task_plan.subtasks, 1):
                yield f"\n\n🚀 Task {i}/{len(task_plan.subtasks)}: {task.objective}\n"

                task_result = await self._execute_research_task(task)
                research_data.append(task_result)
                srcs = task_result.get("sources", [])

                yield f"\n\n✅ Task {i} complete: {len(srcs)} sources found.\n\nSources:\n\n[\n\n"
                for src in srcs:
                    yield f"\n{src},\n"
                yield "\n\n]\n\n"
            # 4. Generate final essay
            if any(result.get("sources") for result in research_data):
                sources = []
                for result in research_data:
                    sources.append(result.get("sources"))
                yield "\n\n📝 Generating comprehensive essay...\n\n"
                # async for chunk in self._generate_final_essay_stream(
                #     research_data, query, sources
                # ):
                #     final_essay += chunk
                #     # yield chunk
                essay = await self._generate_final_essay(research_data, query, sources)
                if essay:
                    # Chunk the essay to mimic streaming response
                    chunk_size = 20  # Characters per chunk
                    delay = 0.01  # Seconds between chunks

                    for i in range(0, len(essay), chunk_size):
                        chunk = essay[i : i + chunk_size]
                        yield chunk
                        await asyncio.sleep(delay)  # Small delay to mimic streaming
            else:
                yield "❌ No research sources found\n"

        except Exception as e:
            yield f"❌ Research failed: {str(e)}\n"
        finally:
            if len(final_essay) > 0:
                yield f"\n\n\n{'='* 16}\nFinal report:\n{'='* 16}\n\n{final_essay}\n\n"

    async def _execute_research_task(self, task: SubTask) -> Dict:
        """Execute a single research task with sequential tool calls"""
        results = {"sources": [], "content": []}

        # Execute each search query sequentially
        for query in task.search_focus:
            try:
                # Use actual web search tool
                search_results = await web_search(query, task.max_search_calls)

                if isinstance(search_results, dict) and search_results.get(
                    "web_results"
                ):
                    for result in search_results["web_results"]:
                        if result.get("url"):
                            results["sources"].append(result["url"])

                            # Fetch content for promising URLs
                            try:
                                content = await web_fetch(result["url"])
                                results["content"].append(
                                    {
                                        "url": result["url"],
                                        "content": content[:2000],  # Limit content size
                                    }
                                )
                            except Exception:
                                continue

            except Exception:
                continue

        return results

    async def _generate_final_essay(
        self,
        research_data: List[Dict],
        query: str,
        sources: List[Dict],
    ) -> str:
        """Generate final essay from research findings"""
        research_summary = json.dumps(research_data, ensure_ascii=False, indent=2)
        sources_serialized = json.dumps(sources, ensure_ascii=False, indent=2)
        prompt = self.prompt_method(research_summary, query, sources_serialized)
        # claude-opus-4-1-20250805
        return self.client.generate_text(
            prompt,
            system="You are an expert academic writer",
            model="claude-sonnet-4-20250514",
            max_tokens=20000,
        )

    async def _generate_final_essay_stream(
        self, research_data: List[Dict], query: str, sources: List[Dict]
    ) -> AsyncGenerator[str, None]:
        """Stream final essay generation"""
        research_summary = json.dumps(research_data, ensure_ascii=False, indent=2)
        sources_serialized = json.dumps(sources, ensure_ascii=False, indent=2)
        prompt = essay_prompt(research_summary, query, sources_serialized)

        async for chunk in self.client.stream_text(
            prompt,
            system="You are an expert academic writer",
            model="claude-sonnet-4-20250514",
            max_tokens=20000,
        ):
            yield chunk

    def _parse_and_validate(self, raw_response: str | dict) -> TaskPlan:
        # claude-3-7-sonnet-20250219 | claude-sonnet-4-20250514 | claude-opus-4-1-20250805
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
                    max_search_calls=min(st.get("max_searches", 1), self.MAX_SUBAGENTS),
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

    def get_article_text(self, url: str):
        article = Article(url)
        article.download()
        article.parse()
        return article.text


qs = [
    # "What are the best ways to treat PCOS symptoms besides birth control?",
    # "which companies may be increasing hiring of software engineers going into 2026?",
    # "globally, what are some of the best cities and/or regions for lesbian US expats right now?",
    # "what tech skills are most going to continue being extremely hireable as AI improves?",
    # "which companies look best positioned to grow over the next 5 years in technology and are worth seeking employment at for junior/mid-level software engineers?"
    # "What are some low-overhead side-business ideas for a busy grad student looking to generate passive income?",
    # "How fast will AI replace econometric modelers?",
    "delicious new york style pizza sauce recipe historical approaches",
    "what are the best treatments for hypermobile Ehlers Danlos Syndrome?"
    # "do caterpillars notice humans and interact with them with curiosity?",
    "I want to go back to school to pursue a Masters Degree (or PhD potentially if relevant) in the intersection of my professional interests. My interests are: Human-Inspired Artificial Intelligence, Applied AI in Neuroscience & Robotics research, AI Engineering, Computational Linguistics, AI Ethics & Alignment. I would likely want to do an online program but am open to in person, and I want to explore options both within and outside of the continental US. What are my options? Please include degree types, cost estimates, admission requirements, and required pre-requisite courses for students without STEM/CS background",
    "are there any scholarships available for prospective students applying to online programs in Master of Science in any( Computational Linguistics, Master of Engineering in Artificial Intelligence & Machine Learning, Master of Science in Artificial Intelligence, MS in AI Ethics and Society) worth applying to? How about for Women? LGBTQ / Trans Women? Non-tech background students? students with ADHD and/or chronic pain? Low-income students?",
]


async def main():
    orchestrator = ResearchOrchestrator(4, essay_prompt) # essay writer instance
    async for result in orchestrator.execute_research(
        qs[random.randint(0, len(qs) - 1)], 3, 3
    ):
        if result:
            print(f"final_response in result from main: {result}")
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
