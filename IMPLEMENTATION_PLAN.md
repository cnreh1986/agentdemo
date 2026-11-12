# Implementation Plan — Personal AI Workforce Studio

## Status legend

- `[ ]` not started
- `[~]` in progress
- `[x]` complete

## Phase 0 — Repository inspection and plan

- [x] Inspect repository (PRD only; no prior app code)
- [x] Create `ARCHITECTURE.md`
- [x] Create `IMPLEMENTATION_PLAN.md`

## Phase 1 — Streamlit UI and Demo Mode

- [x] App layout, theme, navigation
- [x] Task form, samples, mode selector
- [x] Agent roster, workflow view, event feed, output tabs
- [x] Deterministic Demo Mode fixtures and runner
- [x] README, `.env.example`, requirements
- [x] Tests: validation + UI smoke

## Phase 2 — Contracts and agent layer

- [x] Pydantic models for all packets
- [x] Common agent interface
- [x] Four agents + centralised prompts
- [x] Demo provider + validation tests

## Phase 3 — LangGraph orchestration

- [x] StateGraph, states, routing
- [x] Handoffs, events, bounded revision
- [x] Human approval terminal state (graph pause)
- [x] Orchestration tests

## Phase 4 — Live LLM provider

- [x] LiteLLM adapter, readiness, retries
- [x] Mocked live-mode tests

## Phase 5 — Search and evidence

- [x] SearchProvider + Firecrawl (replaced Tavily)
- [x] Unverified labelling; no fabricated URLs
- [x] Injection guards; evidence tests

## Phase 6 — Human approval

- [x] Approve / Reject / Request Revision
- [x] Recorded decisions; human revision re-entry
- [x] Approval tests

## Phase 7 — Persistence, exports, QA

- [x] SQLite history
- [x] Markdown / JSON / ZIP exports
- [x] Workshop metrics; Agent Lab; full acceptance tests
- [x] README finalisation

## Phase reports

### Phase 0
- Files: `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`
- Assessment: empty repo except PRD; Python 3.12 required

### Phase 1–7 (completed)
- Core app under `app.py`, `pages/`, `src/`, `tests/`
- Suite: **32 passed** (`pytest -q`)
- Demo Mode end-to-end with one bounded reviewer revision → human gate
- Live Mode blocked without credentials; LiteLLM adapter with mocked tests
- Optional Firecrawl search; fabricated URLs dropped
- SQLite history + exports with secret sanitisation

### Remaining / known limitations
- Real provider/search calls are manual (not in CI)
- Projector readability should be spot-checked on the workshop laptop
- Human revision after the automatic revision already consumed `max_revisions` hits the limit by design (default 1)
