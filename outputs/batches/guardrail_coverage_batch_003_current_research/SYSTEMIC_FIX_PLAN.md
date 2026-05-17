# Systemic Fix Plan

## P1 - Source Registry Tag Normalization

- Problem: RKLB had sourced current-period/context tags, but snake_case tags were not matched as prose context.
- Affected tickers: RKLB observed; generic for source-registry tag matching.
- File/module: research_agent/quality/deeptech_manual_review.py
- Acceptance test: RKLB early-commercial archetype triggers, RGTI remains speculative deep-tech, no public-ready leak.
- Do-not-touch boundaries: no guard loosening, no ticker hardcoding, no report-template changes.

## P1 - False-Block Candidate Precision

- Problem: IONQ was flagged as high-confidence false block even though current metrics exceeded the speculative deep-tech revenue boundary.
- File/module: research_agent/batch/current_research_recovery.py
- Acceptance test: speculative quantum false-blocks are raised only when current metrics fit the speculative profile.
- Do-not-touch boundaries: no archetype guard loosening, no rating changes, no publishability changes.
