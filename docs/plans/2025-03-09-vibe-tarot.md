# Vibe Tarot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task.

**Goal:** Build a full-stack app where users submit creative direction +
artistic medium, approve a CrewAI-generated style bible, then receive a full
tarot deck (concepts + generated art, per-card vision evaluation and refiner
loop) with zip and print-ready PDF export.

**Architecture:** React SPA frontend; Python FastAPI backend with a job queue
(e.g. Celery + Redis or DB-backed) for style-bible and deck-generation workers;
Postgres (or SQLite MVP); CrewAI for style-bible crew (Style Researcher →
Creative Director → Designer), concept crew (Tarot Scholar + Visual Designer),
vision evaluator, and refiner; external image API for card art; export step for
PDF and zip.

**Tech Stack:** React (Vite), FastAPI, CrewAI, Postgres or SQLite, Redis (if
Celery), image API (TBD, e.g. OpenAI DALL·E), vision-capable LLM for evaluator.

**Spec:** See `docs/plans/2025-03-09-vibe-tarot-design.md`.

---

## Enhancement Summary

**Deepened on:** 2026-03-09  
**Sections enhanced:** 5 phases + cross-cutting (queue, security, performance,
export); **CrewAI Deep Dive** (agents, tasks, structured outputs, vision,
refiner).  
**Research agents used:** architecture-strategist, security-sentinel,
performance-oracle; web + CrewAI docs (crafting agents, tasks, multimodal,
production, kickoff-async).

### Key Improvements

1. **Job queue topology** — Use separate queues for style-bible (fast) vs deck
   generation (long) so short jobs aren’t blocked; document worker scaling and
   idempotency (deck job keyed by deck_id).
2. **Data model** — Add `deck_id` (nullable) on `assets` for deck-level PDF/zip;
   sync status enums (style_bible: draft | generating | ready | approved;
   card/deck as in design) in one place; shared storage (S3/NFS) if running more
   than one worker.
3. **Security** — Validate all IDs as UUIDs; max length on
   creative_direction/medium/feedback; download `type` enum only (zip|pdf);
   resolve files only via DB (no path from client); short-lived signed URLs for
   S3; secrets from env only; sanitize style-bible markdown in frontend.
4. **Performance** — Eager-load deck → cards → assets (avoid N+1); indexes on
   deck_id, card_id, assets.kind; progress via aggregation; batched/parallel
   card processing with concurrency limit; polling with exponential backoff;
   export as separate job/step with timeout; stream or temp files for PDF/zip.
5. **CrewAI** — Use `output_pydantic` / structured outputs for crew outputs;
   optional Task guardrails for style bible and concept; consider Flow wrapper
   and `kickoff_async` for long runs; document rate limits and backoff for
   LLM/image APIs.

### New Considerations Discovered

- **Deck job resume:** On worker crash, deck job should resume from last
  completed card (read card statuses from DB), not restart from card 0.
- **Request-changes:** Clarify whether same style_bibles row is updated (new
  revision) or new row created; keep API and worker consistent.
- **Export:** Define max zip size and image resolution (e.g. 300 DPI for print);
  consider 9-up page size and ~9 pages for 78 cards; allow export-only retry
  without re-running cards.

---

## CrewAI Deep Dive

This section adds implementation detail for all crews and agents, based on
CrewAI docs and best practices. Use it when implementing Tasks 5, 8, 10, and 11.

### Agent Design Principles (80/20 Rule)

- **Spend ~80% of effort on task design, ~20% on agents.** Well-designed tasks
  (clear description, explicit expected_output, single purpose) matter more than
  perfect agent copy.
- **Role–Goal–Backstory:** Every agent should have a **specific role** (e.g.
  "Visual Design Director specializing in brand style guides"), a **goal** with
  success criteria, and a **backstory** that gives domain context and working
  style.
- **Specialists over generalists:** Prefer "Tarot Symbolism Scholar with focus
  on Rider-Waite and Thoth traditions" over "Researcher."
- **Task description = process; expected_output = deliverable.** Description
  says what to do and how; expected_output defines structure, format, and
  quality.

### Structured Outputs and Guardrails

- **Use `output_pydantic` on every crew task** that feeds app logic (style
  bible, card concept, evaluator decision, refiner output). Define Pydantic
  models (e.g. `StyleBibleOutput`, `CardConcept`, `ApproveReject`,
  `RefinedPrompt`). Access result via `result.pydantic` or the task's
  `output.pydantic` in `CrewOutput`.
- **Optional guardrails:** Use `guardrail` (or `guardrails`) to validate before
  accepting. Function-based: `(True, result.raw)` or `(False, "feedback")`.
  LLM-based: pass a string. Set `guardrail_max_retries` (e.g. 3).
- **Task chaining:** Use `context=[previous_task]` when a task needs another's
  output (e.g. Designer task has `context=[research_task, brief_task]`).

### Style-Bible Crew (Task 5)

**Agents:** (1) **Style Researcher** — research artistic medium and visual
traditions; output research notes. (2) **Creative Director** — turn user
direction + research into a coherent creative brief. (3) **Designer** — turn
brief into structured style bible (palette, typography, symbolism, layout,
tone). All with specific role, goal, backstory.

**Tasks (sequential):** `research_task` (inputs: creative_direction, medium) →
`brief_task` (context=[research_task]) → `style_bible_task`
(context=[brief_task]). Use `output_pydantic=StyleBibleOutput` on final task or
store raw markdown. On request-changes:
`kickoff(inputs={..., "feedback": user_feedback})`.

### Concept Crew (Task 8)

**Agents:** **Tarot Scholar** (meaning, symbolism) and **Visual Designer**
(image prompt matching style bible). One or two tasks with `context`; output:
name, meaning, description, image_prompt. Use `output_pydantic=CardConcept` with
those four fields. Task variables: `{style_bible}`, `{card_name}`,
`{card_index}`.

### Evaluator Agent (Task 10) — Vision

- **Single agent with `multimodal=True`** (enables AddImageTool; agent can
  receive image URL or path).
- **Role:** e.g. "Visual Quality Controller for Brand Consistency"; **Goal:**
  Decide if card image matches style bible and concept; output APPROVE or REJECT
  and, if REJECT, short reprompting feedback.
- **Task description:** Include style bible (or summary), card concept, and
  **image URL or path** (e.g. "Evaluate the image at {image_url}..."). Use
  `output_pydantic=ApproveReject` with `decision: Literal["APPROVE","REJECT"]`,
  `feedback: Optional[str]`. Ensure image is accessible (absolute path or signed
  URL) before kickoff.

### Refiner Crew (Task 11)

- **Single agent.** Role: e.g. "Prompt Refinement Specialist"; Goal: update
  image prompt using evaluator feedback and style bible. Task: inputs
  `current_image_prompt`, `evaluator_feedback`, `style_bible`. Use
  `output_pydantic=RefinedPrompt` with `image_prompt: str`,
  `description: Optional[str]`.

### Async and Workers

- **Workers:** Use `crew.kickoff(inputs=...)` (sync) in the worker; no need for
  kickoff_async inside worker. Use `kickoff_async` or `akickoff` only if API ran
  crews in-process (not recommended for long runs).
- **Parallel cards:** Multiple workers (each picks a card) or
  `akickoff_for_each(list_of_inputs)` in an async worker for N concept crews in
  parallel. Use `Process.sequential` for style-bible and concept crews.

### Pydantic Models to Define

- `CardConcept` — name, meaning, description, image_prompt. **ApproveReject** —
  decision, feedback. **RefinedPrompt** — image_prompt, description (optional).
  **StyleBibleOutput** — optional (or store raw string).

### References

- [Crafting Effective Agents](https://docs.crewai.com/en/guides/agents/crafting-effective-agents),
  [Tasks](https://docs.crewai.com/en/concepts/tasks),
  [Multimodal Agents](https://docs.crewai.com/en/learn/multimodal-agents),
  [Production Architecture](https://docs.crewai.com/en/concepts/production-architecture),
  [Kickoff async](https://docs.crewai.com/en/learn/kickoff-async).

---

## Phase 1: Project and data foundation

### Task 1: Backend scaffold and dependencies

**Files:**

- Create: `backend/pyproject.toml` (or `backend/requirements.txt`)
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_main.py`

**Step 1: Create backend directory and dependency file**

Create `backend/requirements.txt` with:

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
crewai>=0.40.0
sqlalchemy>=2.0.0
alembic>=1.13.0
python-multipart>=0.0.6
```

**Step 2: Add minimal FastAPI app**

In `backend/app/main.py`:

```python
from fastapi import FastAPI
app = FastAPI(title="Vibe Tarot API")

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 3: Write failing test**

In `backend/tests/test_main.py`:

```python
from fastapi.testclient import TestClient
from app.main import app

def test_health_returns_ok():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

**Step 4: Run test to verify it fails (or passes if app exists)**

Run:
`cd backend && pip install -r requirements.txt && pytest tests/test_main.py -v`  
If
app not runnable: fix imports so test passes.

**Step 5: Commit**

```bash
git add backend/
git commit -m "chore: add FastAPI backend scaffold and health endpoint"
```

---

### Task 2: Database schema and sessions table

**Files:**

- Create: `backend/app/db.py` (engine, session factory, Base)
- Create: `backend/app/models.py` (SQLAlchemy models: Session, StyleBible, Deck,
  Card, Asset)
- Create: `backend/alembic.ini` and `backend/alembic/env.py` (or manual schema
  script)
- Test: `backend/tests/test_models.py`

**Step 1: Define models per design doc**

In `backend/app/models.py`, define Session (id uuid, created_at, user_id
nullable), StyleBible (id, session_id, status, content, revision, created_at),
Deck (id, session_id, user_id nullable, style_bible_id, status, deck_size,
created_at, updated_at), Card (id, deck_id, position, name, meaning,
description, image_prompt, evaluation_feedback, retry_count, status), Asset (id,
card_id nullable, kind, storage_path, content_type, created_at). Use design doc
types and FKs.

**Step 2: Write failing test**

In `backend/tests/test_models.py`, test creating a Session and a StyleBible
linked to it (use in-memory SQLite), then assert relationships/fields.

**Step 3: Run test** — ensure it fails (e.g. no tables) or passes once schema
exists.

**Step 4: Add DB engine and Base in `backend/app/db.py`**; wire Alembic or a
simple init script to create tables. Run tests again until pass.

**Step 5: Commit**

```bash
git add backend/app/db.py backend/app/models.py backend/alembic* backend/tests/test_models.py
git commit -m "feat: add DB models and schema for sessions, style_bibles, decks, cards, assets"
```

---

### Task 3: Sessions API (create session, get session)

**Files:**

- Create: `backend/app/schemas/session.py` (Pydantic: SessionCreate, SessionOut)
- Create: `backend/app/routers/sessions.py` (POST /sessions, GET /sessions/{id})
- Modify: `backend/app/main.py` (include router, lifespan for DB session)
- Test: `backend/tests/test_sessions_api.py`

**Step 1: Write failing test**

Test POST /sessions returns 201 and session id; GET /sessions/{id} returns same
session or 404.

**Step 2: Run test** — expect fail (no routes).

**Step 3: Implement** — sessions router, schemas, dependency for DB session.
Register router in main. Create session on POST; return session on GET.

**Step 4: Run test** — expect pass.

**Step 5: Commit**

```bash
git add backend/app/schemas backend/app/routers backend/app/main.py backend/tests/test_sessions_api.py
git commit -m "feat: add sessions API (create, get)"
```

### Research Insights (Phase 1)

**Data model (Task 2):**

- Add **`deck_id` (nullable)** on `assets` so deck-level PDF/zip are queryable
  by deck.
- Sync **status enums** with design doc: style_bible
  `draft | generating | ready | approved`; card statuses as in design.
- For multi-worker: **storage must be shared** (S3 or NFS).

**DB performance:** Indexes on `cards.deck_id`, `assets.card_id`, `assets.kind`;
eager loading for deck+cards+assets; progress via aggregation.

**Security:** Use **UUID v4** for session_id and deck_id (no guessable IDs).
Validate all IDs as UUIDs (400 for bad format, 404 after lookup).

---

## Phase 2: Style bible job and crew

### Task 4: Job queue and style-bible job enqueue

**Files:**

- Create: `backend/app/workers/__init__.py`
- Create: `backend/app/workers/queue.py` (abstract or concrete: enqueue
  style_bible job, take job id from DB or queue)
- Create: `backend/app/models/job.py` or add job-related fields to existing
  tables (e.g. style_bible_id + job_status)
- Modify: `backend/app/routers/style_bible.py` or `backend/app/routers/deck.py`
  — endpoint to submit creative direction and enqueue style-bible job
- Test: `backend/tests/test_style_bible_job.py`

**Step 1: Define how jobs are tracked** (e.g. style_bibles table has status
draft/generating/ready; or separate jobs table). Enqueue a “style_bible” task
with session_id and user input (creative_direction, medium, optional deck_size).

**Step 2: Write failing test** — POST with direction + medium creates
style_bible row (or job row) and returns job/session id; status is pending or
generating.

**Step 3: Implement** — queue module (e.g. push to Redis or DB jobs table);
endpoint that creates session if needed, creates style_bible row, enqueues
worker task, returns ids.

**Step 4: Run test** — pass.

**Step 5: Commit**

```bash
git add backend/app/workers backend/app/routers backend/tests/test_style_bible_job.py
git commit -m "feat: enqueue style-bible job from API"
```

---

### Task 5: Style-bible CrewAI crew (Style Researcher → Creative Director → Designer)

**Files:**

- Create: `backend/app/crews/style_bible_crew.py` (agents: Style Researcher,
  Creative Director, Designer; tasks in order; run and return structured style
  bible text/JSON)
- Modify: `backend/app/workers/worker.py` (or wherever worker runs) — call
  style_bible_crew with user input, write result to style_bibles.content and set
  status
- Test: `backend/tests/test_style_bible_crew.py` (unit test with mocked LLM or
  integration with real LLM in CI optional)

**Step 1: Write failing test** — call crew with sample direction + medium;
assert output contains expected sections (e.g. palette, tone) or structure.

**Step 2: Implement crew** — CrewAI crew with three agents, tasks chained:
research → brief → style bible. Parse output into string or JSON for storage.

**Step 3: Worker step** — worker pops style_bible job, loads session + input,
runs crew, updates style_bibles.content and status.

**Step 4: Run test** — pass (mock LLM if needed).

**Step 5: Commit**

```bash
git add backend/app/crews backend/app/workers backend/tests/test_style_bible_crew.py
git commit -m "feat: style-bible CrewAI crew (Style Researcher, Creative Director, Designer)"
```

---

### Task 6: Style-bible approve and request-changes API

**Files:**

- Modify: `backend/app/routers/style_bible.py` — GET style bible by session (or
  job id); POST approve (set status approved); POST request-changes (body:
  feedback, re-enqueue style-bible job with current content + feedback)
- Test: `backend/tests/test_style_bible_approve.py`

**Request-changes behavior (design decision):** Update the **same** style_bibles
row: bump `revision`, set status back to `generating`, enqueue job; when worker
finishes, write new content and set status to `ready`. Do not create a new row.

**Step 1: Write failing tests** — GET returns style bible when ready; POST
approve sets status; POST request-changes bumps revision on same row and
enqueues job.

**Step 2: Implement** — endpoints and DB updates; re-run crew in worker when
request-changes is called (pass current content + feedback).

**Step 3: Run tests** — pass.

**Step 4: Commit**

```bash
git add backend/app/routers backend/tests/test_style_bible_approve.py
git commit -m "feat: style-bible approve and request-changes API"
```

### Research Insights (Phase 2)

**Job queue:**

- Use **separate queues**: e.g. `style_bible` (fast) and `deck` (long) so deck
  jobs don't block style-bible jobs.
- **Celery + Redis:** broker and backend both Redis; set `task_track_started`,
  `max_retries` with exponential backoff; JSON serialization. Long-running crew
  work belongs in workers, not FastAPI request handlers (avoid blocking;
  timeouts).
- **CrewAI production:** Use **structured outputs** (`output_pydantic` or
  `output_json`) for style bible and all crew outputs to avoid parsing errors.
  Consider **Task guardrails** to validate style-bible sections (e.g. minimum
  length). For long runs, use **kickoff_async** and poll; Flows with `@persist`
  allow resume after crash.

**Request-changes (Task 6):** Update the **same** style_bibles row (bump
revision, set status to generating, enqueue job); when worker finishes, set
status to ready. Documented in design doc and Task 6.

**Input validation:** Enforce **max length** on creative_direction (e.g. 2k–10k
chars), medium and feedback (200–500 chars); restrict deck_size to 78 or 22.
Treat user/crew content as untrusted (length limits; no raw HTML when rendering
style bible—sanitize markdown).

**References:**
[CrewAI Production Architecture](https://docs.crewai.com/en/concepts/production-architecture),
[CrewAI Tasks](https://docs.crewai.com/en/concepts/tasks); FastAPI + Celery
integration guides.

---

## Phase 3: Deck generation pipeline

### Task 7: Deck job start and card records

**Files:**

- Create: `backend/app/routers/decks.py` — POST /sessions/{id}/decks or POST
  /decks (body: style_bible_id, deck_size); creates deck row and 78 or 22 card
  rows (status pending)
- Modify: `backend/app/workers/queue.py` — enqueue deck job (deck_id)
- Test: `backend/tests/test_deck_start.py`

**Validation:** Reject deck creation if the given style_bible_id is not in
status `approved`. Return 400 (or 409) with a clear message; do not create deck
or enqueue job.

**Step 1: Write failing test** — POST with approved style_bible creates deck and
N cards; POST with non-approved style_bible returns 400/409. Cards have position
0..N-1, status pending.

**Step 2: Implement** — endpoint + worker enqueue; no crew run yet.

**Step 3: Run test** — pass.

**Step 4: Commit**

```bash
git add backend/app/routers/decks.py backend/app/workers backend/tests/test_deck_start.py
git commit -m "feat: start deck job and create card records"
```

---

### Task 8: Concept crew (Tarot Scholar + Visual Designer) per card

**Files:**

- Create: `backend/app/crews/concept_crew.py` — input: style bible text, card
  index/name (e.g. 0, "The Fool"); output: name, meaning, description,
  image_prompt
- Modify: `backend/app/workers/deck_worker.py` — for a card, call concept_crew,
  update card row (name, meaning, description, image_prompt, status concept)
- Test: `backend/tests/test_concept_crew.py`

**Step 1: Write failing test** — concept_crew("The Fool", 0,
style_bible_snippet) returns dict with keys name, meaning, description,
image_prompt.

**Step 2: Implement** — CrewAI crew with Tarot Scholar and Visual Designer;
single task or two tasks; return structured output.

**Step 3: Wire into deck worker** — for each card in order, run concept crew,
save to card.

**Step 4: Run test** — pass.

**Step 5: Commit**

```bash
git add backend/app/crews/concept_crew.py backend/app/workers backend/tests/test_concept_crew.py
git commit -m "feat: concept crew per card (Tarot Scholar + Visual Designer)"
```

---

### Task 9: Image generation and storage

**Files:**

- Create: `backend/app/services/image_gen.py` — function prompt → call image API
  (TBD: OpenAI or other), save file to local or S3, return storage_path/URL
- Modify: `backend/app/workers/deck_worker.py` — after concept, call image_gen
  with card.image_prompt, save Asset (kind=image, card_id), update card status
- Test: `backend/tests/test_image_gen.py` (mock image API)

**Step 1: Write failing test** — image_gen(prompt) returns path; mock HTTP
client so no real API call.

**Step 2: Implement** — image_gen service; worker step to generate and store
image, link to card.

**Step 3: Run test** — pass.

**Step 4: Commit**

```bash
git add backend/app/services backend/app/workers backend/tests/test_image_gen.py
git commit -m "feat: image generation and asset storage per card"
```

---

### Task 10: Evaluator agent (vision) and approve/reject

**Files:**

- Create: `backend/app/crews/evaluator_crew.py` — input: style bible, card
  concept (name, meaning, description, image_prompt), image (URL or path);
  vision-capable LLM; output: APPROVE or REJECT + feedback string
- Modify: `backend/app/workers/deck_worker.py` — after image generated, call
  evaluator with image; if APPROVE, set card status approved; if REJECT, pass to
  refiner step
- Test: `backend/tests/test_evaluator_crew.py` (mock vision LLM)

**Step 1: Write failing test** — evaluator(style_bible, concept, image_url)
returns {"decision": "APPROVE"|"REJECT", "feedback": "..."}.

**Step 2: Implement** — single vision agent, task to compare image to style
bible and concept; parse output.

**Step 3: Wire into worker** — call evaluator; branch on decision; store
evaluation_feedback on card.

**Step 4: Run test** — pass.

**Step 5: Commit**

```bash
git add backend/app/crews/evaluator_crew.py backend/app/workers backend/tests/test_evaluator_crew.py
git commit -m "feat: vision evaluator agent per card (approve/reject)"
```

---

### Task 11: Refiner and retry loop (Refiner → Image API → Evaluator)

**Files:**

- Create: `backend/app/crews/refiner_crew.py` — input: current image_prompt,
  evaluator feedback, style bible; output: updated image_prompt (and optionally
  description)
- Modify: `backend/app/workers/deck_worker.py` — on REJECT: if retry_count < max
  (e.g. 3), call refiner, update card.image_prompt, increment retry_count, call
  image_gen again, then evaluator again; else mark card failed_retries and keep
  last image or flag
- Test: `backend/tests/test_refiner_crew.py`

**Step 1: Write failing test** — refiner(current_prompt, feedback, style_bible)
returns new prompt string.

**Step 2: Implement** — refiner crew; worker loop: Refiner → image_gen →
evaluator until APPROVE or max retries.

**Step 3: Run test** — pass.

**Step 4: Commit**

```bash
git add backend/app/crews/refiner_crew.py backend/app/workers backend/tests/test_refiner_crew.py
git commit -m "feat: refiner loop (refiner → image API → evaluator)"
```

---

### Task 12: Deck job status and progress API

**Files:**

- Modify: `backend/app/routers/decks.py` — GET /decks/{id} (deck metadata + card
  count by status); GET /decks/{id}/status or /jobs/{id} returning progress
  (e.g. approved_count/total, phase)
- Test: `backend/tests/test_deck_status.py`

**Deck detail for gallery:** GET /decks/{id} returns deck metadata (id, status,
deck_size, style_bible_id, etc.) and, when status is complete, a **cards**
array: each element has card fields (id, position, name, meaning, description,
etc.) and an **asset_url** (or **image_url**) for the card’s image asset (signed
URL or path). Use eager loading (deck → cards → assets) and aggregation for
progress (approved_count/total) so a single GET serves both progress and
gallery. Optional: support GET /decks/{id}?include=cards to include cards only
when needed.

**Step 1: Write failing test** — GET deck returns status and progress (e.g.
23/78 approved); GET deck when complete returns cards with asset URLs.

**Step 2: Implement** — derive from cards.status or job table; return JSON for
UI polling; include cards + asset URLs in GET /decks/{id} when complete (or via
include param).

**Step 3: Run test** — pass.

**Step 4: Commit**

```bash
git add backend/app/routers/decks.py backend/tests/test_deck_status.py
git commit -m "feat: deck job status and progress API"
```

---

### Task 13: Export (PDF + zip) and download URLs

**Files:**

- Create: `backend/app/services/export.py` — build zip of card images + metadata
  JSON; build print-ready PDF (e.g. 9-up); save to storage; create Asset rows
  (kind=pdf, kind=zip, card_id=null for deck-level)
- Modify: `backend/app/workers/deck_worker.py` — when all cards done (approved
  or failed_retries), call export, set deck.status = complete
- Modify: `backend/app/routers/decks.py` — GET /decks/{id}/download?type=zip|pdf
  returns redirect to **short-lived signed URL** (or stream); validate type as
  enum zip|pdf only; resolve asset only via deck_id + type from DB (no
  client-supplied paths).
- Test: `backend/tests/test_export.py` (unit test export with fixture cards)

**Step 1: Write failing test** — export.build_zip(deck_id) produces zip with N
images; export.build_pdf(deck_id) produces PDF.

**Step 2: Implement** — export service; worker calls it; endpoint serves or
redirects to stored file.

**Step 3: Run test** — pass.

**Step 4: Commit**

```bash
git add backend/app/services/export.py backend/app/workers backend/app/routers backend/tests/test_export.py
git commit -m "feat: export deck as zip and PDF, download API"
```

### Research Insights (Phase 3)

**Deck job and workers:**

- **Resume on crash:** Deck job should **resume from last completed card** (read
  card statuses from DB), not restart from card 0; key job by deck_id for
  idempotency.
- **Parallel/batched cards:** Process cards in **batches** (e.g. 4–8 concurrent
  per deck) with a concurrency limit to respect image/LLM rate limits; add
  per-step time targets (e.g. concept &lt; 30s, image &lt; 20s, evaluator &lt;
  15s) to spot bottlenecks.
- **Refiner cap:** After max retries, do not block export—mark card "approved
  with caveats" or "needs_review" and continue; allow export-only retry later.

**Image generation (Task 9):**

- **OpenAI:**
  `client.images.generate(model="dall-e-3", prompt=..., size="1024x1024", n=1)`;
  download image from response URL to storage; use env for API key. Note: DALL-E
  2/3 deprecated May 2026; check for gpt-image-\* alternatives.
- **Rate limits:** Document backoff on 429; consider per-card or per-deck
  throttling.

**Evaluator (Task 10):** Vision models (GPT-4o, Claude) accept image URL or
bytes; support up to ~1.15 MP for optimal tokens; output APPROVE/REJECT +
feedback; parse with guardrail or output_pydantic.

**Export (Task 13):**

- **Download:** Resolve file **only** via deck_id + type (zip|pdf) and DB
  lookup; never use client-supplied paths. Use **short-lived signed URLs** (5–15
  min) if storage is S3.
- **PDF:** ReportLab Canvas for 9-up grid; position images with drawImage; use
  Pillow for resize/thumbnail; define **page size** and image resolution (e.g.
  300 DPI print); 78 cards ≈ 9 pages. Build via **streaming or temp files**, not
  all 78 images in memory.
- **Export as separate step/job:** After all cards done, enqueue **export job**
  (or dedicated step) so deck worker isn't blocked; allows export-only retry.
  Set **timeout** (e.g. 2 min); on timeout mark "export_failed" and allow retry.
  Define **max zip size** (e.g. &lt; 100 MB) and image dimensions.

**Security:** Validate `type` as enum `zip` | `pdf` only; normalize storage_path
and reject `..` and absolute paths; all secrets from env.

**References:** OpenAI image generation API; ReportLab userguide ch2;
Claude/GPT-4 vision docs.

---

## Phase 4: Frontend

### Task 14: Frontend scaffold and start page

**Files:**

- Create: `frontend/` (Vite + React), `frontend/src/App.tsx`,
  `frontend/src/pages/StartPage.tsx`
- Create: `frontend/src/api/client.ts` (fetch wrapper, base URL from env)
- Test: optional `frontend/src/App.test.tsx` or manual

**Step 1: Scaffold** — `npm create vite@latest frontend -- --template react-ts`;
add form: creative direction (textarea), artistic medium (input), deck size
(78|22). On submit, POST to backend (create session + enqueue style-bible job),
store session_id and job/style_bible id in state or URL.

**Step 2: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold and start page (direction, medium, deck size)"
```

---

### Task 15: Style-bible page (view, approve, request changes)

**Files:**

- Create: `frontend/src/pages/StyleBiblePage.tsx` — poll GET style_bible until
  status ready; render content (markdown or sections); buttons: Approve, Request
  changes (modal with feedback input)
- Modify: `frontend/src/App.tsx` — route to StyleBiblePage after start; on
  approve, navigate to deck generation start
- Test: optional

**Step 1: Implement** — polling every 2–5 s; on Approve, POST approve, then POST
create deck (with style_bible_id, deck_size), navigate to progress page. On
Request changes, POST with feedback, stay on page and poll again.

**Step 2: Commit**

```bash
git add frontend/src/pages/StyleBiblePage.tsx frontend/src/App.tsx
git commit -m "feat: style-bible view, approve, request changes"
```

---

### Task 16: Generation progress page and deck gallery + download

**Files:**

- Create: `frontend/src/pages/DeckProgressPage.tsx` — poll GET deck status; show
  progress (e.g. "Card 23/78"); when complete, show gallery (card images) and
  buttons: Download ZIP, Download PDF
- Modify: `frontend/src/App.tsx` — route to DeckProgressPage (deck_id in state
  or URL)
- Test: optional

**Step 1: Implement** — polling GET /decks/{id} (or /decks/{id}/status); on
complete, use the same GET /decks/{id} response which includes cards with
asset_url (see Task 12) to render the gallery. Download buttons open GET
/decks/{id}/download?type=zip|pdf in new tab or trigger download.

**Step 2: Commit**

```bash
git add frontend/src/pages/DeckProgressPage.tsx frontend/src/App.tsx
git commit -m "feat: deck progress page, gallery, and download (zip/PDF)"
```

### Research Insights (Phase 4)

**Polling UX:**

- **Meaningful progress:** Show job states (e.g. Queued, Running, Done, Failed)
  and progress (e.g. "Card 23/78"); avoid indefinite spinners. Return **job/deck
  id** immediately on submit so user sees "Task started" and can poll.
- **Intervals:** Use a **defined strategy**: e.g. 3 s for style-bible, 5 s for
  deck progress; **exponential backoff** for deck (e.g. 3s → 5s → 8s → 15s, cap
  30s) to avoid hammering API during long runs. **Stop polling** when status is
  complete or failed.
- **Decouple logic:** Implement polling in a **custom hook** (or TanStack Query
  with refetchInterval); **pause when tab not visible** to reduce load.
- **TanStack Query:** Use `isFetching` vs initial load for distinct indicators;
  optional conditional GET (ETag) later to reduce payload when unchanged.

**Gallery and download:** GET deck with cards + assets in one or two queries
(eager load); download buttons open signed URL or GET
/decks/{id}/download?type=zip|pdf in new tab; sanitize any crew-rendered content
(markdown) to prevent XSS.

**References:** LogRocket UI patterns for async workflows; TanStack Query
background fetching; Dhiwise React polling guide.

---

## Phase 5: Integration and polish

### Task 17: CORS and env configuration

**Files:**

- Modify: `backend/app/main.py` — add CORS middleware (allow frontend origin
  from env)
- Create: `backend/.env.example` and `frontend/.env.example` (API URL, DB URL,
  image API key placeholders)

**Step 1: Implement** — CORS for frontend; document env vars in README or
.env.example.

**Step 2: Commit**

```bash
git add backend/app/main.py backend/.env.example frontend/.env.example
git commit -m "chore: CORS and env configuration"
```

---

### Task 18: README and run instructions

**Files:**

- Create: `README.md` — project overview, backend (install deps, run migrations,
  start FastAPI, start worker), frontend (install, start dev), env vars,
  optional Docker or single-command run

**Step 1: Write** — clear steps so another dev can run backend + worker +
frontend and generate a deck end-to-end.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with run instructions"
```

### Research Insights (Phase 5)

**CORS:** Allow frontend origin from env (e.g. `VITE_API_ORIGIN` or
`FRONTEND_ORIGIN`); no wildcard in production.

**Env and secrets:** `.env` in `.gitignore`; `.env.example` with placeholders
only (e.g. `OPENAI_API_KEY=`, `REDIS_URL=redis://localhost:6379/0`); document
every variable in README. Production Redis: use strong REDIS_URL with auth; do
not store secrets in Redis.

**README:** Include how to run **more than one worker** and separate queues for
scaling; Docker Compose example (web, worker, Redis, DB) if applicable; Flower
or similar for queue monitoring optional.

---

## Execution

After saving the plan, offer execution choice:

**Plan complete and saved to `docs/plans/2025-03-09-vibe-tarot.md`. Two
execution options:**

**1. Subagent-Driven (this session)** — I dispatch a fresh subagent per task,
review between tasks, fast iteration.

**2. Parallel Session (separate)** — Open a new session with executing-plans,
batch execution with checkpoints.

Which approach?
