# Architecture — Personal AI Workforce Studio

## Purpose

Workshop learning application that demonstrates a coordinated multi-agent workforce. A user submits a task; an Orchestrator runs Research → Planning → Execution → Reviewer with a bounded revision loop, then pauses for explicit human approval. No external side effects (email, calendar, purchases, or system changes).

## Logical layers

```text
Streamlit Presentation Layer (pages/, src/ui/)
        |
        v
Application / Run Controller (src/services/run_service.py)
        |
        v
Orchestrator (LangGraph StateGraph in src/orchestration/)
        |
        +--> Research Agent
        +--> Planning Agent
        +--> Execution Agent
        +--> Reviewer Agent
        +--> Bounded Revision Router
        |
        v
Human Approval Gate (UI + run_service; outside the graph)
        |
        v
Output / Export / History (src/services/, src/persistence/)

Shared:
- Model Provider Adapter (DemoProvider | LiteLLMProvider)
- Search Provider Adapter (optional Firecrawl)
- Pydantic schemas (src/models/)
- Event logger and SQLite run store
- Configuration and secrets (env / st.secrets)
```

## Separation of concerns

| Layer | Responsibility | Must not contain |
| --- | --- | --- |
| UI | Render state, collect input, approval buttons | Agent prompts, provider HTTP, graph edges |
| Run controller | Start/resume runs, record human decisions | Model API calls |
| Orchestration | State machine, handoffs, events, revision routing | Streamlit widgets |
| Agents | Prompts + typed `AgentResult` | Secrets, persistence |
| Providers | LLM/search network adapters | Business workflow rules |
| Persistence | SQLite runs/events/artifacts | API keys |

## Workflow state machine

Required statuses: `IDLE`, `TASK_RECEIVED`, `TASK_VALIDATED`, `SPECIFICATION_CREATED`, `RESEARCH_RUNNING`, `RESEARCH_COMPLETED`, `PLANNING_RUNNING`, `PLANNING_COMPLETED`, `EXECUTION_RUNNING`, `EXECUTION_COMPLETED`, `REVIEW_RUNNING`, `REVISION_REQUIRED`, `REVISION_RUNNING`, `REVIEW_COMPLETED`, `AWAITING_HUMAN_APPROVAL`, `HUMAN_APPROVED`, `HUMAN_REJECTED`, `FAILED`, `CANCELLED`.

Rules:

- Sequential agents only in MVP.
- Reviewer `approved` never sets `HUMAN_APPROVED`.
- Human Approve / Reject / Request Revision are recorded outside the graph.
- Revision count is bounded (`WORKFORCE_MAX_REVISIONS`, default 1).
- Failures preserve completed stage outputs.

## Agent contract

Every agent implements:

```python
def run(self, task: TaskSpec, context: dict) -> AgentResult
```

Outputs are validated with Pydantic before the orchestrator accepts them. Prompts live in `src/config/prompts.py`.

## Providers

- **DemoProvider**: deterministic fixtures; no network; Demo Mode default.
- **LiteLLMProvider**: configurable model ID; keys from env/`st.secrets`; bounded retries; readiness check before Live Mode starts.
- **SearchProvider**: optional Firecrawl (`FIRECRAWL_API_KEY`, POST `/v2/search`). Absent search → research labelled model-knowledge / unverified; no fabricated URLs.

## Persistence and exports

SQLite tables: Run, AgentExecution, WorkflowEvent, Artifact. Ephemeral session mode still works if persistence is disabled or the DB cannot open. Exports: Markdown briefing, JSON run bundle, optional ZIP. Secrets are stripped from events, DB rows, and downloads.

## Safety

- No tools with external side effects.
- Demo Mode never sends prompts to a provider.
- Live Mode discloses that task text is sent to the configured provider.
- Retrieved search text is untrusted and cannot override system instructions.
- Human approval is separate from LLM reviewer approval.

## Runtime

- Python 3.12+ (project `.venv`)
- Streamlit multipage app entry: `app.py` + `pages/`
- Tests: `pytest` under `tests/`
