from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="client"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# fake generator for demo for testing frontend streaming
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
        await asyncio.sleep(0.1)  # simulate delay


@app.get("/")
def home():
    return FileResponse(os.path.join("client", "index.html"))


# demo for testing frontend streaming
@app.get("/demo")
async def stream(msg: str):
    async def event_generator():
        async for token in fake_token_generator(msg):
            yield token

    return StreamingResponse(event_generator(), media_type="text/plain")


if __name__ == "__main__":
    uvicorn.run("app:app", port=5000, log_level="info", reload=True)
