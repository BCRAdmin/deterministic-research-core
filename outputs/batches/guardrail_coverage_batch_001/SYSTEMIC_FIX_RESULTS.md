# Systemic Fix Results - guardrail_coverage_batch_001

## Applied P0/P1 fixes

1. `P1` Data availability status lane for missing provider/source inputs.
   - Files: `research_agent/batch/batch_status.py`, `research_agent/batch/batch_runner.py`, `research_agent/batch/dashboard_adapter.py`, `research_agent/batch/display_policy.py`, tests.
   - Acceptance: missing price/source inputs now produce `status=data_unavailable`, dashboard `data_unavailable=19`, `failed=0`, no publishable/public-ready route.
2. `P1` Archetype priority fix for specific SaaS/semiconductor cues over generic platform language.
   - Files: `research_agent/quality/deeptech_manual_review.py`, archetype tests.
   - Acceptance: DDOG rerun reports `SAAS_CONSUMPTION`; MSFT/GOOGL/SNOW/QCOM/RGTI/RKLB archetype tests remain covered by regression tests.

## Verification run so far

- Targeted tests: `research_agent/tests/test_deeptech_manual_review_profile.py`, `test_archetype_sanity_batch.py`, `test_batch_status.py`, `test_batch_runner.py`, `test_dashboard_adapter.py` passed.
- Batch rerun: `guardrail_coverage_batch_001` completed with `9 passed`, `13 manual_review`, `19 data_unavailable`, `0 failed`.
- Full pytest: `.venv/bin/python -m pytest -q` passed.
- Compileall: `.venv/bin/python -m compileall -q research_agent` passed.
- Vivi schema: `jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())` passed for `vivi_batch_review.json`.

## Do-not-touch boundaries respected

- No guard relaxation.
- No rating relaxation.
- No ticker-specific fallback data.
- No new backbone architecture.
