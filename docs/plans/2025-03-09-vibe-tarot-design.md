# Vibe Tarot — Design Doc

## Goal

Full-stack app that uses CrewAI to take a user's creative direction and artistic
medium and produce a full tarot deck: style bible (user-approved) → card
concepts + generated art (per-card vision evaluation and refiner loop) → export
(zip + print-ready PDF). Session-based first; data model supports accounts
later.

## Architecture

- **Frontend:** React SPA (Vite). Pages: start form → style-bible viewer
  (approve/revise) → generation progress → deck gallery + download.
- **Backend:** Python (FastAPI). REST API for sessions, style bible, deck jobs,
  status polling, downloads. Long-running work in a job queue (e.g. Celery +
  Redis or DB-backed); workers run CrewAI crews, image API, and export.
- **Data:** Postgres (or SQLite for MVP). Tables: sessions, style_bibles, decks,
  cards, assets. All key resources reference `session_id`; `user_id` nullable
  for future accounts.

## User Flow

1. **Start** — User enters creative direction, artistic medium, optional deck
   size (78 or 22).
2. **Style bible** — Backend enqueues job; style-bible crew produces one style
   bible; UI shows it. User approves or requests changes (re-run crew with
   feedback). **Request-changes:** update the same style_bibles row and bump
   revision; do not create a new row.
3. **Deck generation** — On approval, backend enqueues deck job. For each card:
   concept → image → evaluator (vision). If reject: refiner → image API →
   evaluator again (retry cap). Then export (PDF + zip).
4. **Export** — User downloads zip and/or print-ready PDF; deck tied to session
   (re-download during session).

## Data Model

- **sessions** — id (uuid), created_at, user_id (nullable).
- **style_bibles** — id, session_id, status (draft | generating | ready |
  approved), content (markdown/JSON), revision, created_at.
- **decks** — id, session_id, user_id (nullable), style_bible_id, status
  (pending | generating | complete | failed), deck_size, created_at, updated_at.
- **cards** — id, deck_id, position, name, meaning, description, image_prompt,
  evaluation_feedback (nullable), retry_count, status (pending | concept | image
  | evaluating | approved | failed_retries).
- **assets** — id, card_id (nullable for deck-level assets), deck_id (nullable,
  for deck-level pdf/zip), kind (image | pdf | zip), storage_path, content_type,
  created_at.

## CrewAI Agents and Order

### Style-bible crew (Phase 1)

1. **Style Researcher** — Researches artistic medium, visual traditions,
   references; outputs research notes.
2. **Creative Director** — User direction + research → coherent visual/creative
   brief.
3. **Designer** — Brief → structured style bible (palette, typography,
   symbolism, layout, tone). Stored in `style_bibles.content`. On "request
   changes," re-run crew with current bible + feedback.

### Deck generation (Phase 2, per card)

For each card, in order:

1. **Concept crew** — Tarot Scholar + Visual Designer: style bible + card
   index/name → name, meaning, description, image_prompt. Save to `cards`.
2. **Image API** (not an agent) — Generate image from `image_prompt`; store
   image.
3. **Evaluator (Quality Controller, vision)** — Input: style bible + card
   concept + generated image. Output: APPROVE or REJECT + feedback.
4. **Branch**
   - APPROVE → save asset, set card approved, next card.
   - REJECT (under retry limit): **Refiner** updates `image_prompt` (and
     optionally description) from feedback + style bible → **Image API**
     (regenerate) → **Evaluator** again. Cap retries; after max, keep last or
     mark needs review, then next card.

Refiner never talks to Evaluator directly; flow is Refiner → Image API →
Evaluator.

### Export (after all cards)

Build PDF (e.g. 9-up/10-up) and zip from approved cards + assets; store in
`assets`, set `deck.status = complete`.

## Tech Choices

- Image generation: TBD (e.g. DALL·E, Stable Diffusion API).
- Vision for evaluator: Vision-capable LLM (e.g. GPT-4o, Claude with image
  input).
- Storage: Local or S3-compatible for images and exports.
