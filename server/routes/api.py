import asyncio
import json
import time
from orchestrator import ResearchOrchestrator
from fastapi import routing, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

api = routing.APIRouter()


"""/api/"""


@api.get("/api")
def api_default():
    return {"message": "API: oh hey there cutie, didn't see ya there ;)"}


"""/api/research"""


@api.websocket("/api/research")
async def run_research_websocket(websocket: WebSocket):
    print(f'ws cinnex')
    await websocket.accept()
    try:
        # Receive the question from the client
        data = await websocket.receive_text()
        question = json.loads(data).get("question", "") if data else ""
        print(f"Q: {question}")
        if not question:
            await websocket.send_text("Error: No question provided")
            return
            
        orchestrator = ResearchOrchestrator()
        
        async for result in orchestrator.execute_research(question):
            time.sleep(0.5)
            if isinstance(result, str):
                print(result)
                await websocket.send_text(result)
            else:
                print(str(result))
                await websocket.send_text(str(result))
                
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        await websocket.send_text(error_msg)
    finally:
        await websocket.close()


# Keep the original HTTP endpoint for backward compatibility
@api.post("/api/research")
async def run_research(question: str):
    orchestrator = ResearchOrchestrator()
    
    async def event_generator():
        try:
            async for result in orchestrator.execute_research(question):
                if isinstance(result, str):
                    print(result)
                    yield result
                else:
                    print(str(result))
                    yield str(result)
        except Exception as e:
            yield f"Error: {str(e)}"

    return StreamingResponse(event_generator(), media_type="text/plain")


"""/api/demo"""


@api.websocket("/api/demo")
async def stream_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        # Receive the message from the client
        data = await websocket.receive_text()
        user_msg = json.loads(data).get("msg", "") if data else ""
        
        async for token in fake_token_generator(user_msg):
            await websocket.send_text(token)
            
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        await websocket.send_text(error_msg)
    finally:
        await websocket.close()


# Keep the original HTTP endpoint for backward compatibility
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
