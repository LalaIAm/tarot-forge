from fastapi import FastAPI

app = FastAPI(title="Vibe Tarot API")


@app.get("/health")
def health():
    return {"status": "ok"}
