import re
import json
from typing import List, Dict, Any, Optional, Union


def extract_xml(text: str, tag: str) -> str:
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1) if match else ""


def extract_json_from_markdown(raw_response: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw_response, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = raw_response
    return json.loads(json_str)


def prune_brave_search_for_llm(
    search_data: Dict[str, Any], max_results: Optional[int] = 10
) -> str:
    """Prunes Brave search results for LLM analysis"""

    def extract_web_results(web_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key information from web search results"""
        if not web_data or "results" not in web_data:
            return []
        results = []
        web_results = (
            web_data["results"][:max_results] if max_results else web_data["results"]
        )
        for result in web_results:
            pruned_result = {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "description": result.get("description", ""),
                "source": result.get("profile", {}).get("name", ""),
                "age": result.get("age", ""),
                "content_type": result.get("subtype", "generic"),
            }
            results.append(pruned_result)
        return results

    def extract_video_results(video_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key information from video search results"""
        if not video_data or "results" not in video_data:
            return []
        results = []
        for video in video_data["results"]:
            video_info = video.get("video", {})
            pruned_video = {
                "title": video.get("title", ""),
                "url": video.get("url", ""),
                "description": video.get("description", ""),
                "creator": video_info.get("creator", ""),
                "duration": video_info.get("duration", ""),
                "age": video.get("age", ""),
                "platform": video_info.get("publisher", ""),
            }
            results.append(pruned_video)
        return results

    query_info = search_data.get("query", {})
    original_query = query_info.get("original", "")
    web_results = extract_web_results(search_data.get("web", {}))
    video_results = extract_video_results(search_data.get("videos", {}))

    formatted_output = f"""SEARCH QUERY: {original_query}
    
    WEB RESULTS ({len(web_results)} results):
    """
    for i, result in enumerate(web_results, 1):
        formatted_output += f"""
    {i}. {result['title']}
    Source: {result['source']} | Age: {result['age']}
    URL: {result['url']}
    Description: {result['description']}
    Content Type: {result['content_type']}
    """
    if video_results:
        formatted_output += f"\nVIDEO RESULTS ({len(video_results)} results):\n"
        for i, video in enumerate(video_results, 1):
            formatted_output += f"""
    {i}. {video['title']}
    Creator: {video['creator']} | Platform: {video['platform']} | Duration: {video['duration']}
    Age: {video['age']}
    URL: {video['url']}
    Description: {video['description']}
    """
    return formatted_output


def prune_brave_search_json(
    search_data: Dict[str, Any], max_results: Optional[int] = 10
) -> Dict[str, Any]:
    """Prune search results into structured JSON"""
    query_info = search_data.get("query", {})
    pruned_data = {
        "query": query_info.get("original", ""),
        "web_results": [],
        "video_results": [],
    }
    web_data = search_data.get("web", {})
    if web_data and "results" in web_data:
        web_results = (
            web_data["results"][:max_results] if max_results else web_data["results"]
        )
        for result in web_results:
            pruned_data["web_results"].append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "description": result.get("description", ""),
                    "source": result.get("profile", {}).get("name", ""),
                    "age": result.get("age", ""),
                    "content_type": result.get("subtype", "generic"),
                }
            )
    video_data = search_data.get("videos", {})
    if video_data and "results" in video_data:
        for video in video_data["results"]:
            video_info = video.get("video", {})
            pruned_data["video_results"].append(
                {
                    "title": video.get("title", ""),
                    "url": video.get("url", ""),
                    "description": video.get("description", ""),
                    "creator": video_info.get("creator", ""),
                    "duration": video_info.get("duration", ""),
                    "age": video.get("age", ""),
                    "platform": video_info.get("publisher", ""),
                }
            )
    return pruned_data


def plan(**kwargs) -> str:
    prompt = """
    Purpose: Transform user query into actionable research plan
    You are an AI research assistant working as a key analyst in a research workflow that handles research queries and evaluates their complexity in order to plan research sub-tasks which will be delegated to sub-agents.
    The current date is {current_date}
    Query to analyze:
    "{query}"

    Instructions:
    - Categorize query type: straightforward, breadth_first, depth_first
    - Assign complexity score (1-3)
    - Generate subtasks (1-3) with clear boundaries, max searches, expected outputs
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
                "max_searches": 3,
                "priority": "high|medium|low"
            }}
        ]
    }}
    </delegation_format>
    """
    try:
        return prompt.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required prompt variable: {e}")


def essay_prompt(research_findings: str, original_query: str, sources: str):
    return f"""
            You are tasked with writing a comprehensive essay based on a given query and research findings. Your goal is to provide a detailed, impartial, and informative response that addresses the query in depth. Follow these instructions carefully:

            First, review the following research findings:

            <research_findings>{research_findings}
            </research_findings>

            Now, carefully analyze the query:

            <query>
            {original_query}
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

            Citations and references:
            from these sources: {sources}
            1. Use in-text citations whenever you reference information from the research findings.
            2. Format citations as [Source X], where X is the number of the source as listed in the research findings.
            3. If quoting directly, use quotation marks and include the source number.

            Output your essay within <essay> tags. After the essay, provide a list of all sources cited within <sources> tags.

            Important: DO NOT include points as bullets or numbered lists within the essay, the correct format is as if writing an academic paper. If you find yourself tempted to take shortcuts or use shorthand, remember that you are writing for completion and thoroughness.

            Remember to thoroughly address the query, providing a comprehensive and detailed response that synthesizes the information from the research findings.
            """



def pretty(title, ugly_report: dict) -> None:
    """Nicely formats and prints a PCOS dietary/nutrition report dictionary."""
    sources = ugly_report.get("sources", [])
    print("\n" + "=" * 70)
    print(f"\n -- 📋 {title} -- ")
    print("=" * 70 + "\n")
    for thing in ugly_report:
        print(f"\n{thing}")
        for subthing in thing:
            print(f"{subthing}")
    if sources:
        print("🔗 Sources:")
        for i, src in enumerate(sources, 1):
            print(f"  {i}. {src}")
    print("\n" + "=" * 70 + "\n")


def to_markdown(data: Union[str, dict, list]) -> str:
    """Cleans and formats any JSON, string, dict, or list input into readable Markdown"""

    def format_dict(d: dict, indent: int = 0) -> str:
        md = []
        space = "  " * indent
        for k, v in d.items():
            if isinstance(v, dict):
                md.append(f"{space}- **{k}:**")
                md.append(format_dict(v, indent + 1))
            elif isinstance(v, list):
                md.append(f"{space}- **{k}:**")
                md.append(format_list(v, indent + 1))
            else:
                md.append(f"{space}- **{k}:** {v}")
        return "\n".join(md)

    def format_list(lst: list, indent: int = 0) -> str:
        md = []
        space = "  " * indent
        for i, item in enumerate(lst, 1):
            if isinstance(item, dict):
                md.append(f"{space}{i}.")
                md.append(format_dict(item, indent + 1))
            elif isinstance(item, list):
                md.append(f"{space}{i}.")
                md.append(format_list(item, indent + 1))
            else:
                md.append(f"{space}{i}. {item}")
        return "\n".join(md)

    if isinstance(data, str):
        cleaned = data.strip()
        try:
            data = json.loads(cleaned)
        except Exception:
            return f"```\n{cleaned}\n```"
    if isinstance(data, dict):
        return format_dict(data)
    if isinstance(data, list):
        return format_list(data)
    return f"```\n{str(data)}\n```"
