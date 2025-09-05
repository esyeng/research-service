import asyncio
from ..orchestrator import ResearchOrchestrator
from fastapi.responses import StreamingResponse
from fastapi import routing

api = routing.APIRouter()


"""/api/"""


@api.get("/api")
def api_default():
    return {"message": "API: oh hey there cutie, didn't see ya there ;)"}


"""/api/research"""


# @api.get("/api/research")
# def research_get():
#     return {
#         "message": "this is in progress so, please. wait. seriously. i mean it.",
#     }


@api.get("/api/research")
async def run_research(question: str):
    orchestrator = ResearchOrchestrator()
    async def event_generator():
        async for msg in orchestrator.execute_research(question):
            yield msg + "\n"

    return StreamingResponse(event_generator(), media_type="text/plain")
    # return {
    #     "input to llm researcher": question,
    #     "message": "there, happy?",
    # }


"""/api/demo"""


# for testing on fed
@api.get("/api/demo")
async def stream(msg: str):
    async def event_generator():
        async for token in fake_token_generator(msg):
            yield token

    return StreamingResponse(event_generator(), media_type="text/plain")


async def fake_token_generator(user_msg: str):
    words = [
        "Pretend",
        "this",
        "is",
        "an",
        "AI",
        "streaming",
        "tokens...",
        "✨",
        "all",
        "very",
        "impressive.",
    ]
    for w in words:
        yield w + " "
        await asyncio.sleep(0.1)
