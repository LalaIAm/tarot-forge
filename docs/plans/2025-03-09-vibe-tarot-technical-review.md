# Vibe Tarot — Technical Review

**Reviewed:** Plan `docs/plans/2025-03-09-vibe-tarot.md` (18 tasks, 5 phases) and design `docs/plans/2025-03-09-vibe-tarot-design.md`.

---

## Verdict

**Ready for implementation with minor fixes.**

The plan and design are aligned on flow, agent order, and most of the data model. A few design-doc updates and one explicit dependency/clarification are recommended before or during implementation. No blocking gaps.

---

## Strengths

- **Clear flow and phases:** Design and plan agree on style bible → approve → deck job → per-card concept → image → evaluator → refiner loop → export. Agent order (Style Researcher → Creative Director → Designer; then Tarot Scholar + Visual Designer; then Evaluator; then Refiner) is consistent.
- **CrewAI Deep Dive:** Structured outputs (`output_pydantic`), task chaining, vision evaluator, and refiner flow are specified with concrete model names and patterns. Reduces implementation guesswork.
- **Operational detail:** Separate queues (style-bible vs deck), deck job resume from last card, idempotency by `deck_id`, indexes, eager loading, and signed download URLs are called out. Security (UUID validation, no client paths, env-only secrets) is addressed.
- **Test strategy:** Backend has failing-test-first steps; crew tests with mocked LLM; image and export tests with mocks. Covers units and API boundaries.
- **Task ordering:** Dependencies are logically correct (e.g. Task 6 before 7 for approve-before-deck; Task 13 after 12; no circular dependencies).

---

## Issues

### Blocker

- None.

### Major

1. **Design doc vs plan: `style_bibles.status`**  
   Design: `draft | approved`. Plan/Research: `draft | generating | ready | approved`. The plan’s four states are needed (generating = job running, ready = content available for user, approved = user approved). **Recommendation:** Update the design doc Data Model to: `style_bibles.status`: `draft | generating | ready | approved`.

2. **Request-changes: same row vs new row**  
   Plan explicitly leaves open whether request-changes updates the same `style_bibles` row (bump `revision`) or creates a new row. Design does not specify. This affects API and worker behavior. **Recommendation:** Decide (e.g. same row, bump revision) and document in both design and plan so implementation is consistent.

3. **Deck detail for gallery**  
   Plan Task 12 specifies GET deck returns status and progress (e.g. counts). Task 16 and Phase 4 insights require “GET deck cards with asset URLs” for the gallery. The exact contract (e.g. GET `/decks/{id}` with optional `?include=cards,assets` or a separate `/decks/{id}/cards`) is not written down. **Recommendation:** Specify in the plan (and optionally in design) the endpoint and response shape for “deck with cards and asset URLs” so frontend and backend agree.

### Minor

4. **Design doc: `assets` and `deck_id`**  
   Plan adds `deck_id` (nullable) on `assets` for deck-level PDF/zip. Design only has `card_id` (nullable) for deck-level assets. **Recommendation:** Add `deck_id` (nullable) to the design doc `assets` table so schema is the single source of truth.

5. **Task 7: “approve before deck”**  
   Design says “On approval, backend enqueues deck job.” Plan does not state that POST deck must require an approved style bible. **Recommendation:** In Task 7 (or Phase 3), add an explicit step: validate `style_bible_id` is in status `approved` before creating deck and enqueuing; return 400/409 otherwise.

6. **Frontend tests**  
   Tasks 14–16 mark frontend tests as optional. **Recommendation:** Acceptable for MVP; consider at least one smoke test or key flow test (e.g. start → style bible poll) if time allows.

7. **E2E coverage**  
   No single E2E test for “enqueue style-bible job → worker runs → content + ready” or “deck job through concept → image → evaluator → refiner.” Coverage is via unit + API tests. **Recommendation:** Note in plan that E2E is optional/CI later; implement if regression risk grows.

---

## Recommendations (actionable)

1. **Design doc updates (before or in parallel with implementation):**
   - Set `style_bibles.status` to `draft | generating | ready | approved`.
   - Add `deck_id` (nullable) to `assets` in the Data Model.
   - After deciding request-changes behavior: add one line (e.g. “Request-changes: update same row, bump revision” or “create new row”) under style_bibles or User Flow.

2. **Plan clarifications:**
   - **Task 6:** Document the chosen request-changes behavior (same row + revision vs new row) in the task or Phase 2 Research Insights.
   - **Task 7:** Add validation step: “Reject deck creation if style_bible status ≠ approved.”
   - **Task 12 / 16:** Specify the endpoint and response shape for “deck with cards and asset URLs” (e.g. GET `/decks/{id}` with query or nested payload) so the gallery is unambiguous.

3. **Risks and ambiguities (no doc change required, but keep in mind):**
   - **Image API:** Plan notes DALL-E 2/3 deprecation May 2026; image API remains TBD. Proceed with a chosen provider (e.g. OpenAI) and env-based config so swapping is easy.
   - **Rate limits:** Plan already says to document backoff on 429 and consider throttling; implement when integrating LLM/image APIs.
   - **Export:** Max zip size, 300 DPI, 9-up layout, and export-only retry are in the plan; design can stay high-level.

4. **Testability:** Current test steps are sufficient for implementation. Add E2E or frontend tests later if the team wants stronger regression coverage.

---

## Summary

| Criterion           | Result |
|--------------------|--------|
| Completeness       | Plan implements the design; deck-detail-for-gallery contract should be made explicit. |
| Consistency        | Flow, agent order, and card/deck/asset semantics match; style_bible status and assets schema need design doc sync. |
| Design doc gaps    | Update `style_bibles.status` and `assets.deck_id`; document request-changes policy once decided. |
| Task dependencies  | Correct and acyclic; add “approve before deck” validation in Task 7. |
| Testability        | Adequate (unit + API + mocks); E2E and frontend tests optional. |
| Risks/ambiguities  | Request-changes and deck-detail endpoint need decisions; image API and rate limits are acknowledged. |

**Conclusion:** Proceed with implementation. Apply the design doc updates and plan clarifications above so schema, APIs, and worker behavior stay consistent and testable.
