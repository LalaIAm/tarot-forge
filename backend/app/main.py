import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import decks, sessions, style_bible


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Vibe Tarot API", lifespan=lifespan)

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").strip().split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(style_bible.router)
app.include_router(decks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
