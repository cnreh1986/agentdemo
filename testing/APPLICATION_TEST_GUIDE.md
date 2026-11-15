# Application test guide (manual)

Walk the whole app in a browser. Parts A and B need no keys. Part C needs keys.

## 0. Setup

```bash
cd agentDemo
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # first time only; leave keys blank for Parts A–B
streamlit run app.py
```

Open http://localhost:8501. Before starting, run `./testing/run_all_tests.sh` and expect all green.

Optional clean state: delete `data/*.db` (local SQLite for saved tasks and run history).

---

## Part A — Pages (Demo Mode)

### A1. Home Page
1. Open the app. The landing page renders with logo and the workflow description.
2. Sidebar lists: Home Page, Task Manager, Workforce Studio, Run History, Agent Lab, About & Setup.
3. No errors in the terminal.

### A2. Task Manager
1. "System / demo tasks" lists the built-in samples, including the three newer ones:
   - Find product manager jobs in Hyderabad (5–10 years, last 7 days)
   - Compare product manager and product marketer (example company context)
   - Compare product manager and product marketer (needs context)
   Their output formats are "Job search results" or "Comparison matrix". They have no edit controls.
2. Under "Add or edit a task": leave Title empty, click **Save task**. An error says the title is required.
3. Fill Title "My test", Task "Plan my week", leave the rest, click **Save task**. "Task created." and it appears under "Your tasks".
4. Select it in "Select your task to edit", change the Time horizon, **Save task**. "Task updated."
5. Check "I understand…" and click **Delete selected task**. It disappears.
6. Output format dropdown includes "Job search results" and "Comparison matrix".

### A3. Workforce Studio — briefing (regression)
1. Mode is "Demo Mode (default — no API key)".
2. Sample selector → pick a non-job sample (for example the weekly planning one). Fields fill in.
3. No "Interpreted as" panel appears.
4. Click **Run Workforce**. Pipeline advances Orchestrator → Research → Planning → Execution → Reviewer. The activity overlay shows each agent.
5. Run ends awaiting approval. Tabs: Research, Plan, Deliverable, Review, Run Log. Each is populated.
6. Downloads: Markdown, JSON bundle, ZIP, Research (Word). There is **no** CSV button for a briefing.
7. Click **Approve**. Status becomes approved.

### A4. Workforce Studio — job search
1. Pick "Find product manager jobs in Hyderabad (5–10 years, last 7 days)".
2. Panel "Interpreted as: job search" shows Role, City, Min/Max years (5/10), "Posted within" 7, "Accept remote / hybrid" unchecked. A caption states role family `product_management`, Hyderabad IN, overlap policy, last 7 days. A blue info message says Demo Mode uses fixtures.
3. Click **Run Workforce**.
4. **Research** tab: query echo and counts. No web evidence items.
5. **Deliverable** tab:
   - Illustrative banner at the top.
   - Included jobs table with ids `demo-hyd-pm-*`, company, city, posted date, experience, apply link (`example.invalid`).
   - Needs-review table (a row with no stated experience).
   - Excluded rows grouped by reason: out of family, wrong city, stale, no experience overlap.
   - Markdown view sits in an expander.
6. **Review** tab: approved, no blocking issues.
7. Downloads include **Download CSV (included jobs)**. Open it: header `job_id,title,company,city,date_posted,experience,apply_url`; only included jobs.
8. Click **Request Revision** with note "Shorten the summary". A new draft is produced; the table still has only fixture ids.
9. Click **Approve**.

Filter corrections:
10. New Task → pick the job sample again. Change City to "Bengaluru" and Run. Hyderabad rows move to excluded (wrong city).
11. Pick the job sample again. Untick "Apply experience filter" and Run. Needs-review row count changes; no experience exclusions.
12. Set "Posted within" to 0. The caption shows recency "not applied"; a warning lists the filter under "Not applied".
13. Set Min years 40 / Max years 45 and Run. Included table is empty and the exclusion counts explain why. Nothing is invented.

### A5. Workforce Studio — competitive analysis
1. Pick "Compare product manager and product marketer (example company context)".
2. Panel "Interpreted as: competitive analysis": Subjects "Product Manager, Product Marketer", the decision, Audience, a "Context echo" list, constraints, and a green "Context looks sufficient".
3. Run. **Deliverable** tab: illustrative banner, a matrix with rows launch, positioning, enablement, roadmap, metrics, pricing and columns for each subject. Each cell shows a basis label (user supplied / domain default / unknown). No numeric scores.
4. Check these cells: PM release notes / first sales call are "user supplied". PMM current state "no product marketer" is "user supplied". Positioning ownership is labelled "domain default". The pricing company cells are blank, listed under unknowns.
5. Options: hire a product marketer / hire a product manager / defer. No candidate names, no job ad.
6. **Download CSV (matrix cells)**: header `criterion,subject,finding,basis,confidence`.
7. New Task → pick "…(needs context)". The panel shows a yellow "Context is thin…" with questions. Run.
8. Deliverable shows a generic domain frame banner and open questions, with an empty contextual matrix. Review is approved.
9. Edit Background and Constraints to add company details and a decision; the warning turns green. Run again; the matrix fills.

### A6. Workforce Studio — controls
1. **Pause** during a run: "Pause requested". The run stops after the current stage; status shows Paused. **Start** resumes with the same run id.
2. **Reset** → **Confirm reset** clears the run; **Cancel reset** keeps it.
3. **New Task** clears the form and run.
4. Tick "Auto-approve when ready" and run a briefing: it finishes approved, and the activity feed says it came from the setting. Untick it afterwards.
5. **Reject** on a finished run records a rejection.
6. Demo mode with the network disabled still completes.

### A7. Run History
1. After runs above, Run History lists them with mode, status, task.
2. Select a job-search run: pipeline, feed, output tabs render read-only, with the structured job tables.
3. Select a comparison run: matrix renders.
4. Tick "I understand…" and **Clear local history**. The list empties.

### A8. Agent Lab
1. Each agent has an expander with its system prompt.
2. Edit the Research prompt, click **Apply session override**. Success message.
3. Click **Reset**; the default returns. (Overrides are session-only.)

### A9. About & Setup
1. The status block shows `search=…` and `jobs_search=…`. With no key `jobs_search` reads "SerpAPI not configured (Live job_search blocked; Demo Mode unaffected)".
2. A safety bullet says job results come only from the configured source and applying is never automated.
3. The status chip row shows "Jobs: SerpAPI configured" or "SerpAPI not configured (live job search blocked)".

---

## Part B — Live Mode without keys (guard rails)

1. Clear `OPENAI_API_KEY` (and others) and `SERPAPI_API_KEY` in `.env`; restart Streamlit.
2. Switch Mode to "Live LLM Mode". A banner explains Live is blocked until credentials are configured. The app does not fall back to Demo.
3. Select the job sample. The panel shows a red error naming `SERPAPI_API_KEY`. **Run Workforce** is blocked.
4. Select the comparison sample. The panel notes that context goes to your model provider.
5. A briefing task in Live without an LLM key is blocked with a clear message.

---

## Part C — Live Mode with keys

Requires an LLM key and a SerpAPI key (https://serpapi.com). Each search uses SerpAPI credits; a job run makes at most two result pages.

1. In `.env` set `SERPAPI_API_KEY=...` and an LLM key (for example `OPENAI_API_KEY`). Restart.
2. About & Setup shows `jobs_search=` configured. The "Jobs: SerpAPI" chip is green.
3. Live Mode, job sample, Run.
4. Run Log shows the SerpAPI query: `engine=google_jobs`, a Hyderabad location, and the date filter. The key is never printed anywhere (also check the terminal).
5. Included rows each have a real company, description, and an apply link that exists in the SerpAPI result (open a few). No Naukri/LinkedIn scraping occurs.
6. Spot-check filters against the real postings: titles are PM family only, city Hyderabad/known localities, posted ≤ 7 days, experience overlaps 5–10 or sits in needs review.
7. Rows with truncated descriptions are labelled truncated.
8. CSV matches the on-screen included table.
9. Invalid key: set a wrong `SERPAPI_API_KEY`; the run fails or reports the source as failed with a message that does not contain the key. It never produces made-up jobs.
10. Comparison sample in Live: public URLs shown as evidence appear in the Run Log search results; user-supplied cells remain labelled.
11. Run ends at human approval each time.

---

## Part D — Persistence & misc

1. Set `WORKFORCE_PERSISTENCE_ENABLED=false`; Run History shows the "Persistence is disabled" warning.
2. Saved tasks: save a task with output format "Job search results", pick it from the selector under "Saved: …". The "Interpreted as" panel is built from the text again (intents are not persisted).
3. Refresh the browser mid-session: the form resets; history keeps completed runs.

## Pass criteria

- Automated: `./testing/run_all_tests.sh` passes. `--all` shows only the 3 known `tests/test_ui_smoke.py` failures.
- Manual: Parts A and B behave as written. Part C if keys are available.
