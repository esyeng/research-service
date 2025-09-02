from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


app = FastAPI()
app.mount("/", StaticFiles(directory="static", html=True), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return FileResponse("index.html")


if __name__ == "__main__":
    uvicorn.run("app:app --reload", port=5000, log_level="info")
