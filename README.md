# Personal AI Workforce Studio

Streamlit workshop app that demonstrates a coordinated AI workforce:

**User Task → Orchestrator → Research → Planning → Execution → Reviewer → Human Approval → Final Output**

Built for a 60-minute Agentic AI workshop. Demo Mode works offline with no API keys.

## Requirements

- Python 3.12+ (Homebrew `python3.12` on macOS is fine; system 3.9 is not)
- macOS, Windows, or Linux

## Quick start

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Open the local URL Streamlit prints (typically http://localhost:8501).

## Modes

| Mode | Credentials | Behaviour |
| --- | --- | --- |
| **Demo Mode** (default) | None | Deterministic fixtures; no LLM or search network calls |
| **Live LLM Mode** | Provider key via `.env` or `.streamlit/secrets.toml` | LiteLLM adapter (`WORKFORCE_LLM_MODEL`, default `openai/gpt-4o-mini`) |

Live Mode is blocked with a clear error when credentials are missing. The app never silently falls back to Demo Mode.

Optional search: set `FIRECRAWL_API_KEY` (from [firecrawl.dev](https://www.firecrawl.dev/)). Without it, research is labelled model-knowledge / not live-verified and never fabricates URLs.

## Workshop flow

1. Choose Demo Mode (or configure Live Mode).
2. Load a sample task or write your own.
3. Click **Run Workforce**.
4. Watch the pipeline, activity feed, and agent inspector.
5. Inspect Research / Plan / Deliverable / Review tabs.
6. **Approve**, **Request Revision**, or **Reject** (human gate is mandatory).
7. Download Markdown, JSON, ZIP, or Research as a Word (`.docx`) file.
8. Click **New Task** anytime to clear the form and start a custom objective.
8. Reopen runs under **Run History** (local SQLite).

## Tests

```bash
source .venv/bin/activate
pytest -q
```

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Product requirements: [Personal_AI_Workforce_Studio_PRD.md](Personal_AI_Workforce_Studio_PRD.md).

## Safety and limitations

- No emails, calendar changes, purchases, or other external side effects.
- Do not submit passwords, API keys, or confidential data.
- Demo Mode never implies live web research.
- Reviewer scores are model assessments, not objective truth.
- Reviewer “approved” never marks a run human-approved.
- Live API calls are mocked in automated tests; exercise Live Mode manually when a key is present.
- Persistence uses local SQLite under `data/`; clear it from Run History when needed.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `python` too old / Streamlit install fails | Use Python 3.12+ venv |
| Live Mode blocked | Set `OPENAI_API_KEY` (or matching provider key) in `.env` and restart |
| Import errors when running tests | Run from repo root with `pytest` (uses `pythonpath = .`) |
| DB errors | App continues in session mode; delete `data/workforce.db` if corrupted |
