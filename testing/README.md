# Testing pack

Everything here runs offline. No API key, no network: Demo provider, a fake job source, and `httpx.MockTransport` stand in for SerpAPI and Firecrawl.

| File | What it is |
| --- | --- |
| `run_all_tests.sh` | One command for the automated suites. |
| `test_job_search.py` | Job intent parsing, PM-family/city/recency/experience filters, SerpAPI provider, grounding, reviewer checks, graph runs, CSV export. |
| `test_competitive_analysis.py` | Comparison intent, needs-context detection, domain frame, demo matrix, cell bases, options, reviewer checks, graph runs, CSV export. |
| `test_ui_task_classes.py` | Streamlit `AppTest` checks for the "Interpreted as" panel (`st.page_link` is stubbed). |
| `APPLICATION_TEST_GUIDE.md` | Manual, click-by-click walk through every page and the Demo/Live behaviours. |
| `NEWENHANCEMENT_TEST_GUIDE.md` | `newehancement.md` §15 (job search) and §26 (comparison) acceptance criteria mapped to automated tests and manual steps. |

## Run

```bash
./testing/run_all_tests.sh            # new suites + tests/test_orchestration.py
./testing/run_all_tests.sh --all      # everything in tests/ and testing/
./testing/run_all_tests.sh --verbose  # per-test names
```

Or directly:

```bash
source .venv/bin/activate
python -m pytest testing/test_job_search.py testing/test_competitive_analysis.py tests/test_orchestration.py -q --tb=line
```

`pytest.ini` has `testpaths = tests testing`, so plain `pytest` runs both folders.

## Known failures on a clean checkout

`tests/test_ui_smoke.py` has three tests that fail under Streamlit's `AppTest` with
`StreamlitPageNotFoundError: Could not find page: pages/0_Home_Page.py`. The cause is `st.page_link` in the shared page header, which `AppTest` cannot resolve. This predates the task-class work. `testing/test_ui_task_classes.py` avoids it by stubbing `st.page_link`. Use the manual guide to verify those pages in a real browser.

## What is not covered automatically

- A real SerpAPI call. The live path is tested with mock transports only. See Part C of `APPLICATION_TEST_GUIDE.md` for the manual check with a key.
- Live LLM output quality. Live mode needs an LLM key; the tests use fake providers.
