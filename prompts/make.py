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
    try:
        return prompt.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required prompt variable: {e}")


def pretty(ugly_report: dict) -> None:
    """Nicely formats and prints a PCOS dietary/nutrition report dictionary."""
    findings = ugly_report.get("findings", "")
    sources = ugly_report.get("sources", [])
    confidence = ugly_report.get("confidence", None)
    print("\n" + "=" * 70)
    print("📋 Comprehensive PCOS Dietary & Nutritional Intervention Report")
    print("=" * 70 + "\n")
    print(findings.strip() + "\n")
    if confidence is not None:
        print(f"Confidence Score: {confidence*100:.1f}%\n")
    if sources:
        print("🔗 Sources:")
        for i, src in enumerate(sources, 1):
            print(f"  {i}. {src}")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    print('nothin here')
    # pretty(
    #     {
    #         "findings": "Comprehensive PCOS Dietary and Nutritional Intervention Overview:\n\n1. Dietary Approaches:\n- Mediterranean Diet: \n * Most promising dietary intervention for PCOS\n * Shown to improve insulin sensitivity\n * Helps regulate menstrual cycles\n * Reduces androgen levels\n * Effective in restoring menstrual cycle and improving metabolic parameters\n\n- Low Glycemic Index Diet:\n * Helps manage insulin resistance\n * Recommended for 50-75% of PCOS patients with insulin resistance\n * Focuses on low-processed foods and increased protein intake\n\n2. Nutritional Supplements:\n\na) Inositol:\n * Supports weight loss\n * Improves insulin sensitivity\n * May help restore ovulation\n * Helps balance hormones\n * Reduces metabolic syndrome risk\n\nb) Omega-3 Fatty Acids:\n * Reduces chronic inflammation\n * Improves insulin sensitivity\n * Lowers cholesterol and triglyceride levels\n * Helps manage cardiovascular risks\n * May improve menstrual regularity and hormone balance\n\nc) Vitamin D:\n * Supports hormonal balance\n * Helps improve reproductive health\n * Assists in managing PCOS symptoms\n\n3. Key Dietary Recommendations:\n * Prioritize whole foods\n * Reduce refined carbohydrates\n * Increase fiber intake\n * Focus on anti-inflammatory foods\n * Maintain balanced macronutrient profile\n\n4. Additional Insights:\n * Dietary interventions are considered safe and effective\n * Personalized nutrition approaches yield best results\n * Combination of diet and supplements shows most promise",
    #         "sources": [
    #             "https://pubmed.ncbi.nlm.nih.gov/34610596/",
    #             "https://www.hopkinsmedicine.org/health/wellness-and-prevention/pcos-diet",
    #             "https://pmc.ncbi.nlm.nih.gov/articles/PMC8308732/",
    #             "https://pubmed.ncbi.nlm.nih.gov/38388374/",
    #             "https://www.verywellhealth.com/inositol-for-pcos-info-2616286",
    #             "https://pmc.ncbi.nlm.nih.gov/articles/PMC5870911/",
    #             "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5461594/",
    #         ],
    #         "confidence": 0.95,
    #     }
    # )
