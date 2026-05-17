# Quality Score Split Summary

- Batch id: quality_score_split_check
- Scope: Room 16 / Research Agent quality model, dashboard display, report metadata and tests
- Guard changes: none
- Rating changes: none
- Publishability changes from internal score: none

## Implemented Scores

`quality_score.json` now carries:

- `total_score`: legacy score, retained for compatibility
- `publish_quality_score`: strict public/publish readiness score
- `internal_research_quality_score`: internal research usefulness score
- `data_confidence_score`: source/data confidence score
- `score_explanation_short`: short human-readable split rationale

## Dashboard Fields

`dashboard_status.json` per ticker now carries:

- `publish_quality_score`
- `internal_research_quality_score`
- `data_confidence_score`
- `total_score_legacy`
- `score_explanation_short`

Dashboard summary also includes average split scores.

## RKLB Full Run

- Status: manual_review
- Publishable: false
- External display rating: Manual Review / Hold Pending FCF and Execution Evidence
- Company archetype: EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH
- total_score: 65
- publish_quality_score: 65
- internal_research_quality_score: 80
- data_confidence_score: 69

Explanation: Manual review due to negative FCF and extreme valuation; internal report is usable because backlog, revenue scale, FCF path and execution risks are clearly explained.

## Archetype Sanity Split

- RGTI: publish_quality_score 68, internal_research_quality_score 80, data_confidence_score 55, publishable false, Manual Review / Preliminary Underweight
- RKLB sanity case: publish_quality_score 70, internal_research_quality_score 78, data_confidence_score 72, publishable false
- GOOGL: publish_quality_score 92, internal_research_quality_score 92, data_confidence_score 90, publishable true
- SNOW: publish_quality_score 92, internal_research_quality_score 92, data_confidence_score 90, publishable true
- QCOM: publish_quality_score 72, internal_research_quality_score 74, data_confidence_score 62, publishable false, Hold Pending FCF Support

## Verification

- pytest: green
- compileall: green
- RKLB batch: completed_with_issues, no abort
- Archetype sanity batch: completed_with_manual_review
- `publishable` remains false where publish gates block, even when internal_research_quality_score is high
