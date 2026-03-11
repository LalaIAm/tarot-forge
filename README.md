# Vibe Tarot

Generate a custom tarot deck from your creative direction and artistic medium. The app produces a style guide for your approval, then generates card concepts and art (with per-card evaluation and refinement), and lets you download the deck as ZIP or PDF.

**Stack:** React (Vite) frontend, FastAPI backend, CrewAI crews, SQLite (MVP), OpenAI DALL·E 3 for images.

## Quick start

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
```

Copy env (optional; defaults work for local dev). On Windows use `copy .env.example .env` if `cp` is not available.

```bash
cp .env.example .env
# Set OPENAI_API_KEY for image generation. Set DATABASE_URL if not using default SQLite.
```

Start the API:

```bash
uvicorn app.main:app --reload
```

API runs at **http://localhost:8000**. Docs: http://localhost:8000/docs.

### 2. Worker

Jobs (style-bible generation, deck generation) run in a **separate worker process**. In another terminal:

```bash
cd backend
PYTHONPATH=. python run_worker.py
```

Leave it running while you use the app.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**. Set `VITE_API_URL` if your API is not at `http://localhost:8000` (e.g. in `frontend/.env`).

### 4. End-to-end

1. Open http://localhost:5173.
2. Enter creative direction and medium, choose deck size (22 or 78), submit.
3. Wait for the style guide; approve or request changes.
4. After approval, deck generation starts. Progress appears on the deck page.
5. When complete, view the gallery and download ZIP or PDF.

## Environment

| Variable | Where | Description |
|----------|--------|-------------|
| `DATABASE_URL` | Backend | Default: `sqlite:///./vibe_tarot.db` |
| `IMAGE_STORAGE_DIR` | Backend | Card images and exports; default: `backend/uploads` |
| `OPENAI_API_KEY` | Backend | Required for DALL·E 3 card images |
| `CORS_ORIGINS` | Backend | Comma-separated origins; default: `http://localhost:5173` |
| `VITE_API_URL` | Frontend | API base URL; default: `http://localhost:8000` |

See `backend/.env.example` and `frontend/.env.example`.

## Project layout

- **backend/** — FastAPI app, CrewAI crews, workers, DB models, export (zip/PDF).
- **frontend/** — Vite + React app (start → style-bible → deck progress + download).
- **docs/plans/** — Implementation plan and design notes.

## Tests

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

## Limitations / future work

- **Deck job resume:** If the worker stops mid-deck, the next run restarts the deck from card 0. The plan calls for resuming from the last completed card; that is not implemented.
- **Export-only retry:** Re-downloading zip/PDF uses the last built export. There is no “rebuild export only” without re-running card generation.
- **Style-bible rendering:** The style guide is shown as plain text. Markdown rendering (with sanitization) can be added later.
