import datetime
import asyncio
import json
import random
from helpers.llmclient import LLMClient
from helpers.tools import web_search, web_fetch
from helpers.data_methods import plan, essay_prompt, extract_json_from_markdown
from utils.types import SubTask, TaskPlan, TaskDecompositionError
from newspaper import Article
from typing import AsyncGenerator, List, Dict, Callable
from tqdm import tqdm


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
        """researcher execution that only returns final result"""
        final_essay = ""
        try:
            print("run synchronous researcher")
            task_plan = self.analyze_query(query, n_tasks, max_searches)
            if task_plan:
                print("task plan generated, executing tasks...")
            research_data = []
            sources = []
            i = 1
            for task in tqdm(task_plan.subtasks, desc="Executing research tasks", unit="task"):
                print(f"executing task {i}/{len(task_plan.subtasks)}: {task.objective}")
                task_result = await self._execute_research_task(task)
                research_data.append(task_result)
                i += 1
            if any(result.get("sources") for result in research_data):
                for result in research_data:
                    srcs = result.get("sources", [])
                    print(f"\n{len(srcs)} sources found for result!")
                    sources.extend(srcs)
                print("research complete, writing essay...")
                essay = await self._generate_final_essay(research_data, query, sources)
                if essay:
                    final_essay = essay
        except Exception as e:
            print(f"❌ Research failed: {str(e)}\n")
        
        return final_essay

    async def execute_research(
        self, query: str, n_tasks: int, max_searches: int
    ) -> AsyncGenerator[str, None]:
        """Simplified sequential research execution that yields results as it runs"""
        final_essay = ""
        try:
            # 1. start
            yield f"\n\n🔍 Starting research on: {query}\n\n"

            # 2. plan
            yield "\n\n📋 Creating research plan...\n"
            task_plan = self.analyze_query(query, n_tasks, max_searches)
            if task_plan.strategy:
                yield f"\n\n💭 Strategy:\n --> {task_plan.strategy}\n\n"
            research_data = []

            # 3. execute tasks
            for i, task in enumerate(task_plan.subtasks, 1):
                yield f"\n\n🚀 Task {i}/{len(task_plan.subtasks)}: {task.objective}\n"

                task_result = await self._execute_research_task(task)
                research_data.append(task_result)
                srcs = task_result.get("sources", [])

                yield f"\n\n✅ Task {i} complete: {len(srcs)} sources found.\n\nSources:\n\n[\n\n"
                for src in srcs:
                    yield f"\n{src},\n"
                yield "\n\n]\n\n"
            # 4. write essay
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
                    # mimic streaming response
                    chunk_size = 20
                    delay = 0.01

                    for i in range(0, len(essay), chunk_size):
                        chunk = essay[i : i + chunk_size]
                        yield chunk
                        await asyncio.sleep(delay)
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
        for query in task.search_focus:
            try:
                search_results = await web_search(query, task.max_search_calls)
                if isinstance(search_results, dict) and search_results.get(
                    "web_results"
                ):
                    for result in search_results["web_results"]:
                        if result.get("url"):
                            results["sources"].append(result["url"])

                            # fetch content of promising URLs
                            try:
                                content = await web_fetch(result["url"])
                                results["content"].append(
                                    {
                                        "url": result["url"],
                                        "content": content[:2000],  # limit content size
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

