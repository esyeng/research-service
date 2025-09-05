import uvicorn
import os
from .routes.api import api
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
client_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "client"))
app.mount("/client", StaticFiles(directory=client_path), name="client")
app.include_router(router=api)
# app.mount("/api", api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return FileResponse(os.path.join("client", "index.html"))


if __name__ == "__main__":
    uvicorn.run("app:app", port=5000, log_level="info", reload=True)
