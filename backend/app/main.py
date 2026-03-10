from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routers import sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Vibe Tarot API", lifespan=lifespan)

app.include_router(sessions.router)


@app.get("/health")
def health():
    return {"status": "ok"}
