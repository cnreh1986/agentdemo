# Product Requirements Document (PRD)
# Personal AI Workforce Studio
**Product:** Personal AI Workforce Studio  
**Document type:** Product Requirements Document + Cursor Agent Build Specification  
**Version:** 1.0  
**Status:** Ready for implementation planning  
**Primary UI:** Streamlit  
**Backend language:** Python  
**Primary use:** 60-minute hands-on Agentic AI workshop  
**Primary users:** Product Breakfast attendees; Product Managers, Product Leaders, Founders, Business Analysts, Engineers, Consultants and AI enthusiasts.

---

## 1. Executive Summary

Personal AI Workforce Studio is a Python application with a Streamlit user interface that demonstrates how a coordinated team of specialised AI agents can complete a meaningful task. It must make agent activity observable: participants should see what each agent is doing, what input it received, what output it produced, what it handed to the next agent, where review occurs, and where a human must approve the final result.

The core demonstration is a Personal Productivity Workforce. A user submits a task such as researching a topic, prioritising skills, creating a five-day plan and producing a briefing. An Orchestrator coordinates four specialist agents:

1. Research Agent — discovers and organises evidence.
2. Planning Agent — converts findings into a prioritised plan.
3. Execution Agent — creates the requested deliverable.
4. Reviewer Agent — independently evaluates quality and requests revisions when needed.

The Orchestrator is the workflow coordination layer, not necessarily a fifth specialist agent. A human remains the final decision-maker.

The product is designed for a 60-minute workshop. It must be easy to launch, resilient to missing credentials, visually understandable to non-technical attendees, and sufficiently extensible for technical participants to inspect prompts, schemas, workflow state and agent handoffs.

**Important product boundary:** This is a workshop learning application, not an autonomous enterprise agent platform. It must not perform consequential external actions such as sending emails, publishing content, purchasing goods, changing calendars or modifying business systems. It generates drafts and recommendations for human review.

## 2. Product Vision

Help people move from using AI as a chatbot to delegating bounded work to a transparent, coordinated AI workforce.

### Product promise
"Give your task to a team of specialised AI agents. Watch them research, plan, create, challenge and prepare the work for your approval."

### Experience principles
- **Visible, not magical:** show agent state, handoffs and outputs.
- **Useful, not theatrical:** each agent must have a distinct responsibility and meaningful deliverable.
- **Human-directed:** the user defines the task and approves the result.
- **Evidence-aware:** distinguish verified evidence, model-generated reasoning, assumptions and unknowns.
- **Workshop-friendly:** provide a reliable demo mode and preconfigured defaults.
- **Provider-flexible:** isolate model-provider integrations behind an adapter.
- **Inspectable:** expose prompts, input packets, output packets, events, timing and errors.
- **Safe by default:** no external side effects in the MVP.

## 3. Goals and Non-Goals

### 3.1 Goals
1. Let a participant submit a task in plain language.
2. Execute a visible, stateful, multi-agent workflow.
3. Show the Orchestrator and four specialist agents as distinct stages.
4. Show live status changes and a timestamped activity feed.
5. Display the inputs and outputs exchanged at each handoff.
6. Generate a structured final briefing and action plan.
7. Run an independent quality review.
8. Support a bounded revision loop.
9. Require explicit human approval before marking the result approved.
10. Support Demo Mode without API credentials.
11. Support Live LLM Mode through a configurable model adapter.
12. Provide downloadable outputs and an execution report.
13. Be simple enough to use in a 60-minute workshop.

### 3.2 Non-goals for MVP
- Sending emails, messages or calendar invitations.
- Making purchases, payments or financial transactions.
- Autonomous changes to external applications or databases.
- Long-term personal memory across sessions.
- Multi-user authentication, tenancy and role-based administration.
- Production-grade deployment, billing or subscription management.
- Complex parallel agent execution.
- A general-purpose no-code workflow builder.
- Fully autonomous web browsing unless a search adapter is explicitly implemented and enabled.
- Guaranteeing factual correctness from an LLM.
- Building a full observability platform.

## 4. Target Users and Personas

### Persona A: Product Manager / Product Leader
Needs competitor research, product opportunity briefs, roadmap thinking and meeting preparation. Wants to understand delegation and quality controls without becoming an AI engineer.

### Persona B: Founder / Consultant
Needs market research, client briefing, business planning and structured recommendations. Values speed, evidence and a clear final deliverable.

### Persona C: Engineer / Technical Participant
Wants to inspect orchestration, agent contracts, state transitions, prompts, model calls and failure handling. May extend the code.

### Persona D: Business Analyst / General Professional
Wants to convert an ambiguous work request into research, an action plan and a presentable document.

### Persona E: Student / Early-Career Participant
Wants learning plans, career research and a guided workflow that demonstrates practical AI delegation.

## 5. Core User Journey

1. User opens the application.
2. User sees a short explanation of the workforce and the four agents.
3. User selects Demo Mode or Live LLM Mode.
4. User enters a task or selects a sample task.
5. User optionally adds context, constraints, preferred output and time horizon.
6. User clicks **Run Workforce**.
7. Orchestrator validates the task and creates a task specification.
8. Research Agent runs and returns a structured research packet.
9. Planning Agent receives the task and research packet and returns an action plan.
10. Execution Agent receives the task, research and plan and creates a deliverable.
11. Reviewer Agent independently reviews the deliverable against the original task and evidence.
12. If review requests changes, Orchestrator routes a bounded revision to the relevant stage and repeats review.
13. Once the review passes or the revision limit is reached, the workflow pauses for human review.
14. User inspects the outputs and review report.
15. User selects **Approve**, **Request Revision**, or **Reject**.
16. User downloads the final briefing and run report.

## 6. Functional Requirements

Priority definitions:
- **P0:** Must-have for workshop MVP.
- **P1:** Important if time allows; should be included if practical.
- **P2:** Future enhancement.

### FR-01: Application launch and landing state — P0
- Display product name: Personal AI Workforce Studio.
- Display tagline: From AI Assistant to Agentic AI That Gets Work Done.
- Explain in 2–3 sentences what the application does.
- Show the five workflow components: Orchestrator, Research, Planning, Execution, Reviewer.
- Explain that human approval is required.
- Provide a clear primary task input and Run Workforce action.
- Display a visible setup/status area indicating selected execution mode and provider readiness.
- App must load into a usable state even when no model credentials exist.

Acceptance criteria:
- App launches with no API key.
- User can understand the workflow from the landing screen without reading external documentation.
- Primary action is visually obvious.

### FR-02: Execution modes — P0
Provide two modes:
1. **Demo Mode:** runs deterministic, clearly labelled illustrative outputs; no API key required.
2. **Live LLM Mode:** calls a configured LLM provider through an adapter.

Requirements:
- Mode selection must be visible.
- Demo Mode must be the default.
- Live mode must check provider configuration before execution.
- Missing credentials must produce an actionable, non-crashing error.
- The UI must clearly label model-generated output as unverified unless evidence retrieval and verification are enabled.
- Demo Mode must never imply that it performed live web research.

Acceptance criteria:
- Demo Mode runs end-to-end without credentials.
- Live mode reports missing configuration before beginning.
- The app does not silently switch from Live to Demo.

### FR-03: Task input — P0
Fields:
- Task / objective (required).
- Optional background/context.
- Optional constraints (budget, time, audience, geography, preferred format).
- Optional time horizon.
- Output format (Briefing, Action Plan, Research Summary, Markdown bundle).
- Sample task selector.

Validation:
- Task must be non-empty.
- Apply configurable maximum input length.
- Trim whitespace.
- Warn users not to enter passwords, API keys, sensitive personal data or confidential business information.
- Provide at least three sample tasks:
  - Plan my next productive week.
  - Research a product opportunity and prepare a brief.
  - Create a learning roadmap for a new skill.

Acceptance criteria:
- Invalid task cannot be submitted.
- Sample task populates the task field and can be edited.
- Optional fields may be left blank.

### FR-04: Orchestrator — P0
Responsibilities:
- Create a unique run ID.
- Validate and normalise task input.
- Convert user request into a Task Specification.
- Define success criteria and expected deliverables.
- Determine the next workflow stage.
- Pass only necessary context to each agent.
- Track workflow state, attempt count and errors.
- Route reviewer feedback to a bounded revision.
- Stop when approved, rejected, failed or maximum revisions reached.
- Never bypass human approval.

Task Specification fields:
- run_id
- original_task
- objective
- background
- constraints
- time_horizon
- requested_output
- success_criteria
- created_at
- execution_mode
- model_configuration (non-secret metadata only)

Acceptance criteria:
- Orchestrator produces a visible task summary.
- Run state is inspectable.
- Agent order is deterministic in the MVP.
- Workflow stops safely on unrecoverable errors.

### FR-05: Research Agent — P0
Responsibilities:
- Interpret the research question.
- Identify relevant themes and questions.
- Use configured search tools only when available.
- Separate verified source-backed facts from model-generated synthesis and assumptions.
- Capture source title, URL, publisher/domain, retrieval timestamp and a short supporting excerpt/summary when available.
- Highlight conflicting information and evidence gaps.
- Never fabricate citations, URLs, quotes, dates or statistics.
- If no search tool is configured, explicitly state that the output is based on model knowledge and is not live-verified.

Research Packet schema:
- run_id
- research_question
- key_findings[]
- evidence_items[]
- assumptions[]
- uncertainties[]
- risks[]
- open_questions[]
- research_limitations[]
- status
- agent_summary

Evidence Item schema:
- claim
- source_title
- source_url
- source_domain
- retrieved_at
- supporting_excerpt_or_summary
- evidence_type (primary, secondary, model_synthesis, user_supplied)
- confidence (high, medium, low, unknown)

Acceptance criteria:
- Research output has explicit limitations.
- Sources are only displayed if returned by a configured tool or supplied by the user.
- No fabricated source URLs.
- Research packet is visible and downloadable/inspectable.

### FR-06: Planning Agent — P0
Inputs:
- Original task and Task Specification.
- Research Packet.
- User constraints.

Responsibilities:
- Translate findings into actionable steps.
- Prioritise actions by impact, urgency and effort.
- Identify dependencies, risks and decision points.
- Create a realistic sequence and timeline.
- Define measurable outcomes.
- Mark assumptions and unsupported recommendations.

Plan schema:
- objective
- strategic_rationale
- priorities[]
- actions[]
- timeline[]
- dependencies[]
- risks[]
- assumptions[]
- success_metrics[]
- open_decisions[]

Action item fields:
- action_id
- title
- description
- priority (high, medium, low)
- estimated_effort
- suggested_timing
- dependency_ids[]
- expected_outcome
- evidence_refs[]
- owner (default: user)

Acceptance criteria:
- Plan is traceable to the original task and research packet.
- Actions are concrete and ordered.
- Unknown dates or effort are not invented; use estimates clearly labelled as estimates.

### FR-07: Execution Agent — P0
Inputs:
- Task Specification.
- Research Packet.
- Plan.

Responsibilities:
- Create the requested deliverable.
- Preserve source traceability.
- Distinguish recommendation, evidence and assumption.
- Use clear headings and concise professional language.
- Include next steps and unresolved questions.
- Do not introduce unsupported facts.
- Return Markdown and structured metadata.

Deliverable schema:
- title
- executive_summary
- objective
- key_findings[]
- recommendations[]
- action_plan[]
- resources[]
- assumptions[]
- unresolved_questions[]
- evidence_references[]
- markdown_content
- status

Acceptance criteria:
- Final output is readable in the UI.
- User can download Markdown.
- Output reflects the task and plan.
- Evidence references map to the research packet.

### FR-08: Reviewer Agent — P0
Inputs:
- Original task and success criteria.
- Research Packet.
- Plan.
- Execution deliverable.

Responsibilities:
- Independently evaluate completeness, relevance, clarity and evidence support.
- Identify unsupported claims and fabricated-looking citations.
- Check whether recommendations address the task.
- Check that actions are practical and traceable.
- Return explicit approve/revision/reject recommendation.
- Provide actionable correction instructions.
- Do not simply trust the Execution Agent.

Review schema:
- status (approved, revision_required, rejected, unable_to_review)
- quality_score (0–100)
- criteria_results[]
- issues[]
- missing_information[]
- unsupported_claims[]
- recommendations[]
- revision_targets[]
- reviewer_summary

Suggested review criteria:
- Task alignment.
- Completeness.
- Evidence quality and traceability.
- Actionability.
- Internal consistency.
- Clarity and usability.
- Assumption transparency.
- Safety and human approval.

Acceptance criteria:
- Reviewer output is shown separately from the deliverable.
- Any score is presented as an LLM assessment, not an objective truth.
- Revision request identifies specific fields or sections to change.
- Reviewer cannot approve external actions.

### FR-09: Bounded revision loop — P0
- Configure maximum revision cycles; default 1 for workshop.
- Reviewer can request revision or approve for human review.
- Orchestrator routes revision instructions to the relevant agent/stage.
- Preserve original and revised outputs.
- Display revision count and reason.
- Stop after maximum revision count; present unresolved issues to the human.
- Never create an unbounded loop.

Acceptance criteria:
- Reviewer can request one revision.
- Revision count is visible.
- Workflow terminates at the configured limit.
- The user can still inspect and decide on a result that needs revision.

### FR-10: Human approval — P0
At the end of workflow, present:
- Final deliverable.
- Review status and score.
- Outstanding issues and uncertainties.
- Explicit buttons: Approve, Request Revision, Reject.

Rules:
- Approval means the user accepts the generated deliverable for their own use; it does not trigger an external action.
- Request Revision should allow a short instruction.
- Reject marks the run rejected and retains its history.
- No action may be taken outside the application.

Acceptance criteria:
- Workflow cannot be marked user-approved without a human click.
- Approval decision, timestamp and optional note are recorded.
- Rejection and revision are also recorded.

### FR-11: Live activity feed — P0
Display timestamped events:
- Run created.
- Task validated.
- Orchestrator completed task specification.
- Agent queued / started / completed / failed.
- Handoff created and validated.
- Reviewer requested revision / passed review.
- Human approval requested / approved / rejected.
- Run completed / failed / cancelled.

Each event should include:
- event_id
- run_id
- timestamp
- stage
- event_type
- status
- human-readable message
- duration_ms where applicable
- safe metadata (no secrets)

Acceptance criteria:
- Events appear in chronological order.
- Current agent is visually identifiable.
- Failure events show a useful error message without exposing credentials or stack traces to normal users.
- UI refreshes while the workflow is executing.

### FR-12: Workflow visualisation — P0
Show a clear pipeline:
User Task → Orchestrator → Research → Planning → Execution → Reviewer → Human Approval → Final Output.

Node states:
- Waiting
- Queued
- Running
- Completed
- Needs revision
- Failed
- Skipped

Requirements:
- Active node visually highlighted.
- Completed nodes visually differentiated.
- Failed nodes show a safe error state.
- Revision path is visible.
- Do not imply parallel execution in the sequential MVP.

### FR-13: Agent inspector — P0
For each agent, provide tabs or expandable sections:
- Role and responsibility.
- System instructions/prompt (sanitised, no secrets).
- Input packet.
- Output packet.
- Status.
- Start/end timestamps and duration.
- Error/retry information.
- Handoff destination.

Acceptance criteria:
- User can inspect every completed agent.
- Raw JSON and human-readable summary are both available.
- Secrets and provider credentials are never displayed.

### FR-14: Final outputs and export — P0
Provide:
- Final briefing rendered in Markdown.
- Research packet.
- Action plan.
- Review report.
- Run summary / event log.
- Download options: Markdown for final deliverable; JSON for structured run bundle; optionally ZIP containing all outputs.

Acceptance criteria:
- Downloaded content matches displayed content.
- File names include a safe run identifier and timestamp.
- Export excludes API keys and secrets.

### FR-15: Session history — P1
- Persist completed and failed runs locally using SQLite.
- List previous runs by date, task title, mode and status.
- Reopen a run in read-only inspection mode.
- Do not retain raw secrets.
- Provide a clear "Clear local history" action with confirmation.

### FR-16: Accessibility and responsive layout — P1
- Use readable typography and adequate contrast.
- Do not rely on colour alone for status; include text and icons.
- Support common laptop viewport sizes.
- Keep primary task action visible without excessive scrolling.
- Use clear labels and helpful empty states.
- Avoid dense technical language in the default view; place advanced details in inspector/expander sections.

## 7. UI / UX Specification

### 7.1 Navigation
Use a simple Streamlit multipage or tab-based structure:
1. **Workforce Studio** — primary task and live run.
2. **Run History** — prior runs (P1).
3. **Agent Lab** — inspect/edit agent instructions for workshop learning (P1).
4. **About & Setup** — providers, setup status, safety notes and architecture.

For the MVP, a single page with clear sections and tabs is acceptable if navigation complexity threatens workshop reliability.

### 7.2 Main page layout
Top header:
- Personal AI Workforce Studio.
- Tagline.
- Short explainer.
- Mode selector and provider status.

Task workspace:
- Task text area.
- Context and constraints expander.
- Sample task selector.
- Output format.
- Run Workforce primary button.
- Reset button (confirm if a run is active).

Workforce overview:
- Orchestrator card.
- Four specialist agent cards.
- Each card shows icon, name, one-line role, state and duration.

Main monitoring area:
- Left: workflow visualisation and event timeline.
- Right: current stage, stage summary and agent inspector.

Output area:
- Tabs: Research, Plan, Deliverable, Review, Run Log.
- Final approval panel appears when review is ready.

### 7.3 Visual design
- Professional, modern workshop dashboard.
- Light theme default; do not make the screen visually crowded.
- Use a restrained palette: deep slate/navy text, teal/green for completed, amber for review-needed, red for errors, neutral grey for waiting.
- Use cards, status chips, progress indicators and expandable details.
- Keep labels consistent.
- Use icons as supporting cues, not as the only status indicator.
- Ensure the agent pipeline is understandable from a distance on a projector.

### 7.4 Streamlit implementation guidance
- Use `st.session_state` for current run state and selected run.
- Use `st.status`, `st.progress`, `st.empty`, `st.tabs`, `st.expander`, `st.columns` and `st.download_button` where appropriate.
- Do not block the entire UI without feedback during a long run.
- Streamlit rerun behaviour must be handled deliberately. Use a controlled run state and a safe execution approach.
- For a simple workshop MVP, synchronous sequential execution with visible status updates is acceptable. For robust incremental updates, use a queue/background worker and polling or an event stream, but do not introduce fragile concurrency without tests.
- Avoid unsafe HTML injection. If custom HTML/CSS is used, keep it static and sanitised.
- All secrets must be read from `st.secrets` or environment variables; never hardcode them.

## 8. Technical Architecture

### 8.1 Recommended logical architecture

```text
Streamlit Presentation Layer
        |
        v
Application / Run Controller
        |
        v
Orchestrator (LangGraph StateGraph)
        |
        +--> Research Agent
        |
        +--> Planning Agent
        |
        +--> Execution Agent
        |
        +--> Reviewer Agent
        |
        +--> Bounded Revision Router
        |
        v
Human Approval Gate
        |
        v
Output / Export Service

Shared services:
- Model Provider Adapter (LiteLLM or provider adapters)
- Search Provider Adapter (optional; only if configured)
- Pydantic schemas and validation
- Event Logger / Run Store (SQLite)
- Configuration and Secrets
```

### 8.2 Recommended repository structure

```text
personal-ai-workforce/
├── app.py
├── pages/
│   ├── 1_Workforce_Studio.py
│   ├── 2_Run_History.py
│   ├── 3_Agent_Lab.py
│   └── 4_About_Setup.py
├── src/
│   ├── config/
│   │   ├── settings.py
│   │   └── prompts.py
│   ├── agents/
│   │   ├── base.py
│   │   ├── research_agent.py
│   │   ├── planning_agent.py
│   │   ├── execution_agent.py
│   │   └── reviewer_agent.py
│   ├── orchestration/
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── routing.py
│   │   └── runner.py
│   ├── models/
│   │   ├── task.py
│   │   ├── research.py
│   │   ├── plan.py
│   │   ├── deliverable.py
│   │   ├── review.py
│   │   └── events.py
│   ├── providers/
│   │   ├── llm_base.py
│   │   ├── litellm_provider.py
│   │   └── search_base.py
│   ├── services/
│   │   ├── run_service.py
│   │   ├── export_service.py
│   │   └── history_service.py
│   ├── persistence/
│   │   ├── database.py
│   │   └── repositories.py
│   └── ui/
│       ├── components.py
│       ├── workflow_view.py
│       ├── agent_cards.py
│       └── output_views.py
├── tests/
│   ├── test_schemas.py
│   ├── test_agents.py
│   ├── test_orchestration.py
│   ├── test_revision_loop.py
│   ├── test_exports.py
│   └── test_ui_smoke.py
├── .streamlit/
│   └── config.toml
├── .env.example
├── requirements.txt
├── README.md
└── PRD.md
```

Cursor may simplify this structure for the first build, but it must preserve separation between UI, agent logic, orchestration, provider adapters, schemas and persistence.

### 8.3 Orchestration state machine

Required states:
- IDLE
- TASK_RECEIVED
- TASK_VALIDATED
- SPECIFICATION_CREATED
- RESEARCH_RUNNING
- RESEARCH_COMPLETED
- PLANNING_RUNNING
- PLANNING_COMPLETED
- EXECUTION_RUNNING
- EXECUTION_COMPLETED
- REVIEW_RUNNING
- REVISION_REQUIRED
- REVISION_RUNNING
- REVIEW_COMPLETED
- AWAITING_HUMAN_APPROVAL
- HUMAN_APPROVED
- HUMAN_REJECTED
- FAILED
- CANCELLED

Transitions:
- Task received → validation.
- Validation failure → return actionable validation error.
- Validation success → create specification.
- Specification → Research → Planning → Execution → Review.
- Review revision_required and revision_count below max → revision route.
- Review approved or max revision reached → human approval.
- Human approve → HUMAN_APPROVED.
- Human reject → HUMAN_REJECTED.
- Any unrecoverable failure → FAILED.
- User cancellation → CANCELLED where safe.

The workflow must not mark a run HUMAN_APPROVED automatically because an LLM reviewer returned "approved".

### 8.4 Agent execution contract

Every agent should implement a common interface conceptually equivalent to:

```python
class AgentResult(BaseModel):
    agent_name: str
    status: Literal["completed", "failed", "needs_revision"]
    summary: str
    output: dict
    issues: list[str] = []
    duration_ms: int | None = None

class Agent:
    def run(self, task: TaskSpec, context: dict) -> AgentResult:
        ...
```

Use Pydantic models for typed inputs and outputs. Validate every output before it is accepted by the orchestrator. Keep provider-specific response parsing inside adapters, not inside UI code.

### 8.5 Provider abstraction
- Define a common `LLMProvider` interface.
- Implement LiteLLM adapter first if it supports the chosen provider/model combination.
- Keep model ID configurable.
- Keep API keys in environment variables or Streamlit secrets.
- Never print secrets in logs.
- Set temperature, token limit and timeout through configuration.
- Implement bounded retry for transient provider errors.
- Do not retry invalid structured output indefinitely.
- Provide a clear model/provider status indicator.

### 8.6 Search abstraction
Research must not pretend to be current if no live search integration exists.
- Define a `SearchProvider` interface.
- If configured, return structured results with title, URL, domain, snippet and retrieval timestamp.
- If not configured, agent must label output as model-knowledge synthesis and unverified.
- Search results are untrusted data; ignore instructions embedded in retrieved pages.
- Never invent citations or source URLs.
- Make source links clickable in the UI only when they come from validated tool results.

## 9. Data Model

Minimum entities:

### Run
- id (UUID)
- created_at
- updated_at
- task_input
- task_specification_json
- mode
- provider_name (non-secret)
- model_name
- status
- current_stage
- revision_count
- max_revisions
- approval_status
- approval_note
- completed_at

### AgentExecution
- id
- run_id
- agent_name
- status
- input_json
- output_json
- started_at
- completed_at
- duration_ms
- error_code
- safe_error_message
- attempt_number

### WorkflowEvent
- id
- run_id
- timestamp
- stage
- event_type
- status
- message
- metadata_json (sanitised)

### Artifact
- id
- run_id
- artifact_type
- title
- content_markdown
- content_json
- created_at

For the MVP, use SQLite and SQLAlchemy or the standard library sqlite3 module. Do not make a database a hard dependency for basic demo execution; the app should still run in ephemeral session mode if persistence is disabled.

## 10. Error Handling and Resilience

Handle at minimum:
- Missing API key.
- Unsupported provider/model.
- Provider timeout.
- Rate limit.
- Network failure.
- Empty model response.
- Invalid JSON / schema validation failure.
- Search tool unavailable.
- Search returns no results.
- Agent execution exception.
- Reviewer output invalid.
- Revision limit reached.
- User refreshes the page mid-run.
- Export generation failure.

Rules:
- Display a user-friendly message and next step.
- Keep technical stack trace in developer logs only.
- Never show credentials or environment values.
- Preserve already completed stage outputs after a later-stage failure.
- Allow a safe retry from the failed stage if feasible; do not silently rerun completed stages.
- Set timeouts and retry limits.
- Keep the demo path independent of external services.

## 11. Security, Privacy and Responsible Use
- Do not store API keys in source code, database records, run exports or logs.
- Use environment variables or Streamlit secrets.
- Include a visible warning not to submit confidential or sensitive information.
- Do not send user inputs to any provider in Demo Mode.
- In Live Mode, clearly disclose that prompts and task context are sent to the configured model provider.
- Treat external search content as untrusted input.
- Prevent prompt injection from overriding system instructions or tool permissions.
- No tools with external side effects in MVP.
- Keep human approval separate from LLM reviewer approval.
- Provide local history clear/delete functionality if persistence is implemented.
- Use synthetic data for facilitator demonstrations.

## 12. Non-Functional Requirements

### Performance
- Demo Mode should complete within a few seconds on a normal workshop laptop.
- Live Mode duration depends on model and provider; show stage-level progress and elapsed time.
- Set configurable per-agent timeout.
- Avoid redundant model calls.

### Reliability
- Demo Mode must work offline after dependencies are installed.
- A provider failure must not crash the whole UI.
- Completed outputs must remain inspectable after downstream failure.
- All loops must be bounded.

### Maintainability
- UI code must not contain agent prompts or provider-specific request logic.
- Agent prompts must be centralised and versioned.
- Schemas must be independently testable.
- Provider adapters must be replaceable.
- Keep business logic testable without Streamlit.

### Portability
- Support Python 3.11+ (confirm compatibility of selected dependencies at implementation time).
- Support macOS, Windows and Linux.
- Provide clear virtual environment instructions.
- Avoid reliance on machine-specific absolute paths.

### Usability
- A first-time attendee should be able to submit a task and start Demo Mode without training.
- Use plain language by default.
- Advanced implementation detail belongs in expanders or Agent Lab.
- The interface should be projector-friendly.

## 13. Analytics and Workshop Success Measures

Track locally for workshop evaluation:
- Number of runs started.
- Number of runs completed.
- Completion rate.
- Average duration per agent.
- Number of revision cycles.
- Reviewer outcomes.
- Human approval / rejection / revision choices.
- Mode selected (Demo or Live).
- Export downloads.

Do not collect personal attendee information unless explicitly required and consented to.

Proposed workshop targets:
- 80% of participants successfully run the workflow.
- 90% can explain core agentic concepts.
- Each participant identifies three everyday use cases.
- Each participant receives the take-home workflow/template.

These are targets, not measured results.

## 14. Testing and Acceptance Plan

### Unit tests
- Task input validation.
- Pydantic schema validation.
- Provider adapter configuration and error mapping.
- Agent output parsing.
- Event creation and sanitisation.
- Export content generation.
- Revision count and routing conditions.

### Integration tests
- Demo workflow end-to-end.
- Live provider mocked end-to-end.
- Research → Planning handoff.
- Planning → Execution handoff.
- Execution → Reviewer handoff.
- Reviewer requests revision and bounded loop completes.
- Reviewer approves and workflow pauses for human approval.
- Provider failure preserves completed outputs.
- Missing search provider labels research unverified.

### UI smoke tests
- Application starts.
- Demo Mode is available without credentials.
- Sample task populates task input.
- Run action starts workflow.
- Activity feed appears.
- Agent output tabs render.
- Approval controls appear at correct stage.
- Downloads work.

### Critical acceptance scenarios
1. **No credentials:** User opens app, selects Demo Mode, runs sample task, sees all agents complete, inspects outputs and downloads briefing.
2. **Live provider configured:** User runs task, sees provider and model label, receives outputs from each agent.
3. **Provider missing:** Live mode is blocked with a clear setup message; no crash.
4. **Reviewer revision:** Reviewer flags an unsupported recommendation; orchestrator requests one bounded revision; revised result is reviewed again.
5. **Revision limit:** If the reviewer still requests changes after maximum attempts, run pauses for human decision and reports unresolved issues.
6. **Human approval:** User explicitly approves or rejects; decision and timestamp are recorded.
7. **No live search:** Research output clearly says it is not live-verified and contains no fabricated source links.
8. **Failure:** An agent fails; previous outputs remain available and the UI explains which stage failed.

## 15. Build Plan for Cursor Agent

Build in phases. Do not attempt to generate the entire application in one unreviewed pass.

### Phase 0 — Repository inspection and plan
- Inspect existing repository before modifying anything.
- Identify existing app, dependencies, environment and code conventions.
- Preserve useful existing work.
- Create `IMPLEMENTATION_PLAN.md` and `ARCHITECTURE.md`.
- List assumptions, dependency versions and risks.
- Do not delete files without justification.

### Phase 1 — Foundation and UI shell
- Create app layout, theme and navigation.
- Add task form, sample tasks and execution mode selector.
- Add agent roster, workflow diagram placeholder, event feed and output tabs.
- Implement Demo Mode with deterministic fixture outputs.
- Add README and `.env.example`.
- Confirm app starts without credentials.

### Phase 2 — Contracts and agent layer
- Implement Pydantic models.
- Implement common agent interface.
- Implement four agents with prompts separated from code.
- Add fake/demo provider and mock tests.
- Validate all agent outputs.

### Phase 3 — Orchestration
- Implement LangGraph StateGraph (or a clearly isolated sequential runner if LangGraph is intentionally deferred).
- Implement explicit states and transitions.
- Add handoff packets and event emission.
- Add bounded reviewer revision loop.
- Add human approval state.

### Phase 4 — Live LLM provider
- Implement LiteLLM adapter.
- Add secrets/config handling.
- Add timeouts, retries and safe error mapping.
- Add provider readiness checks.
- Test with mocked responses before real API calls.

### Phase 5 — Search integration and evidence handling
- Implement optional SearchProvider interface.
- Add one provider only if credentials and access are available.
- Validate and store source metadata.
- Ensure research clearly labels unverified model knowledge when search is unavailable.
- Add prompt-injection protections for retrieved content.

### Phase 6 — Persistence, exports and polish
- Add SQLite run history if time permits.
- Add Markdown and JSON exports.
- Add optional ZIP export.
- Improve UI feedback, responsive layout and accessibility.
- Add event/run timing.

### Phase 7 — QA and workshop rehearsal
- Run automated tests.
- Test on target Mac and a second laptop/browser.
- Test projector readability.
- Rehearse a complete 60-minute run.
- Test Wi-Fi/API failure fallback.
- Freeze build and publish setup instructions.

## 16. Definition of Done

The MVP is ready for the workshop only when:
- App launches locally using documented commands.
- Demo Mode works without credentials.
- Task input and sample tasks work.
- Orchestrator creates and displays a task specification.
- Four specialist agents execute in the correct order.
- Each handoff is visible and schema-validated.
- Live activity feed updates during execution.
- User can inspect agent inputs and outputs.
- Reviewer performs a distinct review.
- Revision loop is bounded.
- Human approval is explicit and recorded.
- Final briefing can be downloaded.
- No API key is exposed in UI, logs or exports.
- No external side effects are possible in MVP.
- Critical acceptance scenarios pass.
- README includes setup, configuration, known limitations and troubleshooting.

## 17. Cursor Agent Instructions

You are acting as a senior Python engineer, AI systems architect and Streamlit product engineer. Build Personal AI Workforce Studio according to this PRD.

Mandatory working rules:
1. Read this entire PRD before coding.
2. Inspect the current repository and existing files first.
3. Produce an implementation plan before making broad changes.
4. Do not replace working code without understanding it.
5. Use modular Python architecture and type hints.
6. Use Pydantic schemas for all inter-agent contracts.
7. Keep UI, orchestration, agents, providers, prompts and persistence separate.
8. Implement Demo Mode first; it must be reliable without API credentials.
9. Implement Live LLM Mode behind a provider abstraction.
10. Never hardcode credentials or expose secrets.
11. Do not claim live research unless a search adapter actually ran and returned sources.
12. Keep all agent loops and retries bounded.
13. Never add external side-effect tools to the MVP.
14. Add automated tests as each phase is implemented.
15. Keep the UI understandable to non-technical workshop participants.
16. Show meaningful agent activity, input/output handoffs, status and errors.
17. Preserve completed stage outputs if a later stage fails.
18. Update README, architecture and implementation status as the code evolves.
19. Do not leave core requirements as TODOs while claiming the build is complete.
20. At the end of each phase, report files changed, tests run, test results, limitations and next phase.

First response expected from Cursor:
- Repository assessment.
- Proposed architecture mapped to this PRD.
- Dependency and version plan.
- Phased implementation plan.
- Risks, assumptions and questions that block implementation.

Then implement Phase 1 and continue phase-by-phase, running tests and reporting progress. Do not silently skip requirements.
