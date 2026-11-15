#!/usr/bin/env bash
# Run the Personal AI Workforce Studio test suites.
#
# Usage:
#   ./testing/run_all_tests.sh            # new task-class suites + orchestration (default)
#   ./testing/run_all_tests.sh --all      # every test in tests/ and testing/
#   ./testing/run_all_tests.sh --verbose  # default suites, per-test output
#
# No network, no API keys: Demo provider, fake job source, and httpx MockTransport only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

# Make sure no real key leaks into a test run.
unset SERPAPI_API_KEY FIRECRAWL_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY || true

MODE="${1:-default}"
case "$MODE" in
  --all)
    echo "== Full suite (tests/ + testing/) =="
    python -m pytest tests testing -q --tb=short
    ;;
  --verbose)
    python -m pytest testing/test_job_search.py testing/test_competitive_analysis.py \
      testing/test_ui_task_classes.py tests/test_orchestration.py -v --tb=short
    ;;
  default|"")
    echo "== job_search + competitive_analysis + orchestration =="
    python -m pytest testing/test_job_search.py testing/test_competitive_analysis.py \
      testing/test_ui_task_classes.py tests/test_orchestration.py -q --tb=line
    ;;
  *)
    echo "Unknown option: $MODE (use --all, --verbose, or no argument)" >&2
    exit 2
    ;;
esac
