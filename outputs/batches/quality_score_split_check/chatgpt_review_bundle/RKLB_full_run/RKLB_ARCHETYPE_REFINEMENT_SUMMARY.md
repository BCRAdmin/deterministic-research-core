# RKLB Archetype Refinement Summary

- Batch id: rklb_archetype_refinement_check
- Ticker: RKLB
- Mode: source_ingestion_mode
- Price basis date: 2026-05-15
- Status: manual_review
- Publishable: false
- Internal rating: Hold
- External display rating: Manual Review / Hold Pending FCF and Execution Evidence
- Quality score: 65
- Publish quality score: 65
- Internal research quality score: 80
- Data confidence score: 69

## Archetype Result

- company_archetype: EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH
- speculative_deep_tech_profile_count: 0
- early_commercial_capital_intensive_tech_count: 1
- archetype_confidence: 1.0

Triggered rules:

- revenue_ttm_gt_100m
- revenue_ttm_lt_5b
- operating_income_ttm_lt_0
- free_cash_flow_ttm_lt_0
- market_cap_revenue_gt_20
- ev_sales_gt_20
- backlog_contracts_or_contracted_missions_present
- capital_intensive_development_program_present
- major_execution_milestone_risk_present
- product_platform_still_scaling
- beta_high_volatility
- current_period_evidence_exists_but_fcf_path_negative

## RKLB Regression Read

RKLB no longer falls into the older speculative deep-tech class for the current bundle values. The new class recognizes real revenue, backlog/contracts and operating history, while still blocking clean publication because FCF, valuation and execution evidence are not strong enough.

The report main text now covers:

- backlog above 2.2B
- TTM revenue 622.5M
- Q1 revenue 200.3M
- Space Systems/product revenue vs Launch Services/service revenue
- Electron/HASTE contracts, launch manifest and Neutron risk
- FCF -220.1M
- EV/Sales 118.78x
- technical setup only as a short timing note
- valuation sensitivity around EV/Sales 118.78x, backlog conversion, Neutron delay and persistent FCF losses

## Internal Best Report

`internal_best_report.md` is now the readable manual-review surface for the early-commercial capital-intensive tech profile and starts with `# Rocket Lab (RKLB) — Interne Research-Lesefassung`. `final_report.md` can remain claim-ledger-like; `internal_best_report.md` has no claim IDs or source labels in the main body, keeps source labels in the Evidence Appendix, and includes Statusbox, Executive Summary, the required RKLB operating sections, Valuation / Sensitivity, Final Internal View and Follow-up Checklist.

RKLB internal_best_report includes TTM revenue 622.5M, Q1 revenue 200.3M, backlog above 2.2B, Space Systems 127.5M, Launch Services 72.9M, FCF -220.1M, cash/securities 1.48B, EV/Sales 118.78x, Electron/HASTE/contracts and Neutron execution risk. The unclear `revenue growth of 63.5%` language is removed from the readable main body unless a period/source-qualified version is available.

## Publish Stub

Because RKLB remains `publishable=false`, `publish_report.md` is now a publication stub / manual-review surface, not a normal public report. Dashboard and public-library state remain `publishable=false`; the stub points reviewers to the internal best report and preserves valuation sensitivity without presenting a clean public recommendation.

## Quality Counter Check

- mechanical_rating_language_count: 0
- publish_mechanical_language_count: 0
- publish_valuation_sensitivity_present: 1
- source_ingestion_post_audit_block_count: 1

## Quality Score Split

The legacy `total_score` remains 65 for compatibility, but RKLB now exposes separate score intent:

- `publish_quality_score`: 65
- `internal_research_quality_score`: 80
- `data_confidence_score`: 69
- `score_explanation_short`: Manual review due to negative FCF and extreme valuation; internal report is usable because backlog, revenue scale, FCF path and execution risks are clearly explained.

The internal score does not affect `publishable`; RKLB remains `publishable=false`.

## Remaining Manual Review Reasons

- EXTREME_VALUATION_REQUIRES_REVIEW
- EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE
- EARNINGS_DATE_UNAVAILABLE
- PERIOD_TYPE_MISMATCH_IGNORED
- TRUE_SOURCE_VALUE_DISAGREEMENT
- SOURCE_FRAME_VARIANT_IGNORED

Financial-sanity classification is now valuation-risk based: EV/Sales 118.78x is treated as a clean extreme multiple that requires review, not as a period denominator bug. These are not guard-loosening candidates. They keep the run in manual_review.

## Acceptance State

- Batch abort: no
- RKLB hardcoded in production classification logic: no
- Deep-Tech guard loosened: no
- PERIOD_DENOMINATOR_BUG on RKLB EV/Sales: no
- EXTREME_VALUATION_REQUIRES_REVIEW on RKLB EV/Sales: yes
- internal_best_report readable surface: yes
- internal_best_report main body claim IDs/source labels: no
- internal_best_report title: Rocket Lab (RKLB) — Interne Research-Lesefassung
- publish_report public-style report: no
- publishable remains false: yes
- mechanical_rating_language_count=0: yes
- publish_mechanical_language_count=0: yes
- publish_valuation_sensitivity_present=1: yes
- quality score split present: yes
- internal_research_quality_score can exceed publish_quality_score without changing publishable: yes
- QCOM display rule: covered by regression tests
- RGTI/IONQ/QBTS speculative deep-tech: covered by regression tests
- GOOGL/SNOW/MSFT unaffected: covered by regression tests
- pytest: green
- compileall: green
- artifact consistency: clean
- review bundle: outputs/batches/rklb_archetype_refinement_check/chatgpt_review_bundle.zip
