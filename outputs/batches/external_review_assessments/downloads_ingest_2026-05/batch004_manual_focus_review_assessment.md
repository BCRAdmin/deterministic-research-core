# Batch 004 Manual-Focus Review Assessment

## Reviewed bundles

Uploaded bundles reviewed:

- `chatgpt_manual_focus_review_bundle.zip`
- `chatgpt_manual_review_bundle.zip`

Primary focus: `IONQ`, `NVDA`, `QBTS`, `QCOM`, `RGTI`.

## Executive verdict

Batch 004 is technically stronger than earlier batches, but the focused manual-review bundle reveals several system-level issues that should be fixed before relying on this as a stable operating baseline.

The important finding is not that the system failed. The important finding is that the manual-focus sample exposed four durable guardrail problems:

1. QCOM appears to be a likely false pass.
2. IONQ is likely misclassified as `STANDARD_GROWTH`.
3. weekend/non-trading-day price freshness is being treated as a manual-review reason.
4. internal research scores are inflated for weak-data manual-review reports.

RGTI/QBTS are mostly correctly blocked, but their internal-best reports are still generic and not at the same quality level as the earlier RGTI gold internal note.

---

## 1. QCOM is the highest-priority issue

### Observed

QCOM is marked:

- `status = passed`
- `publishable = true`
- `external_display_rating = Accumulate`
- `quality_score = 87`

But the report itself states:

- `FCF TTM = Metric unavailable in available evidence`
- `P/FCF = Metric unavailable in available evidence`
- true unresolved source disagreements = `25`
- `data_confidence_score = 68`
- `data_ops_priority_note` says QCOM is P0 and still needs direct IR/earnings release or 10-Q extract.

### Why this is a problem

Earlier we explicitly created the QCOM rule:

> If FCF support is missing, QCOM should not surface as a plain Accumulate. It should show `Manual Review / Hold Pending FCF Support` or equivalent.

This batch appears to regress that behavior.

### Expected

QCOM should be one of:

- `manual_review / Hold Pending FCF Support`, if FCF support is still missing; or
- passed only if current-period FCF/OCF support is now actually present and mapped.

Current artifact evidence points to missing FCF support, so current `passed / Accumulate` is likely a false pass.

### Required fix

Re-enable or harden the QCOM missing-FCF support guard generically:

- no plain `Accumulate` when FCF is unavailable;
- missing FCF should not count as a positive cash-conversion claim;
- publishability should block or at least require manual review when FCF support is required by the ticker/archetype.

Priority: **P0**.

---

## 2. IONQ is likely misclassified

### Observed

IONQ is marked:

- `company_archetype = STANDARD_GROWTH`
- `archetype_confidence = 0.2`
- `status = manual_review`
- `external_display_rating = Hold`

Key values in the internal report:

- revenue TTM = `$132.8M`
- FCF TTM = `$-233.3M`
- SBC/Revenue = `146.2%`
- EV/Sales = `132.41x`
- P/FCF unavailable

### Why this is a problem

IONQ is not a normal standard-growth company. It is a quantum / frontier-tech company with real revenue, negative FCF, very high valuation and large dilution/stock-comp pressure.

It also should not necessarily be treated exactly like RGTI, because revenue is above the very-low-revenue threshold. The better classification is likely:

- `EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH`, or
- a quantum/frontier-tech variant of that class.

### Expected

IONQ should not be `STANDARD_GROWTH` unless the classifier has a strong reason. At minimum, it should be flagged for archetype review.

### Required fix

Add/adjust classifier logic:

- companies with `revenue_ttm > 100M`, negative FCF, high EV/Sales, high SBC/revenue and frontier-tech/quantum context should not default to `STANDARD_GROWTH`;
- map such cases to `EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH` if they have real revenue but still speculative economics;
- preserve RGTI/QBTS as `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL` when their data fits.

Priority: **P1**.

---

## 3. Price freshness is not trading-calendar aware

### Observed

Manual-review reasons include:

- `PRICE_DATE_BEFORE_AS_OF_DATE`

for IONQ, NVDA, QBTS and RGTI.

But the bundle uses:

- report date / as-of date around `2026-05-17`
- price basis date `2026-05-15`

2026-05-17 is a Sunday. A Friday close on 2026-05-15 is expected and should be fresh if no later trading day exists.

### Why this is a problem

This creates false manual-review pressure. Price date before report date is normal over weekends and market holidays.

### Expected

Freshness should compare against the latest available trading day, not calendar date alone.

### Required fix

Implement trading-calendar-aware freshness:

- if report/as-of date is weekend or holiday, latest prior trading close is fresh;
- do not add `PRICE_DATE_BEFORE_AS_OF_DATE` as a manual-review reason if the price is from the latest available trading session;
- keep stale-price blocking only when a newer trading session should exist.

Priority: **P1**.

---

## 4. Internal research quality score is inflated

### Observed

Examples:

- IONQ: `internal_research_quality_score = 100`, `data_confidence_score = 60`, manual review with multiple issues.
- NVDA: `internal_research_quality_score = 100`, `data_confidence_score = 53`, manual review with true source disagreements and FCF anomaly.
- QCOM: `internal_research_quality_score = 100`, but FCF unavailable and true source disagreements = 25.

### Why this is a problem

A manual-review report can have high internal usefulness, but `100` is too high when key facts are unresolved or FCF/current-period evidence is missing.

### Expected

Internal score should be allowed to exceed publish score, but not max out when evidence confidence is weak.

Suggested cap rules:

- if `data_confidence_score < 60`, cap `internal_research_quality_score <= 85`;
- if manual review reasons include source disagreement / FCF anomaly / missing earnings date, cap `internal_research_quality_score <= 90`;
- if the internal-best report is generic template prose, cap lower.

Priority: **P1**.

---

## 5. RGTI/QBTS block correctly, but internal report rendering regressed

### Observed

RGTI and QBTS correctly remain manual review.

RGTI:

- `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL`
- `Manual Review / Preliminary Underweight`
- `publishable = false`

QBTS:

- same deep-tech classification and preliminary underweight framing.

### Problem

The internal-best reports are generic template reports, not the higher-quality RGTI-style internal lesefassung previously created.

RGTI internal report currently contains generic sentences such as:

- revenue scale language,
- FCF generic caveats,
- technical timing language,
- and does not look like the German RGTI gold internal note.

### Expected

For `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL`, internal best report should use the archetype-specific manual-review template:

- Technology Reality Check
- Commercial Adoption
- Contract / Order Materiality
- Financial Reality
- Accounting Quality
- Valuation Disconnect
- Final Internal View

Priority: **P2** for this batch, because status blocking is correct; but important for report quality.

---

## 6. NVDA manual review is acceptable

NVDA manual review is not necessarily wrong. It has:

- `SEMICONDUCTOR_AI_INFRA`
- manual review reasons around FCF anomaly, true financial anomaly, source frame/period issues and true source disagreement.

Given NVDA’s size and AI-infrastructure importance, this needs direct IR/current-period context before promotion. Manual review is acceptable.

However, the internal research score of 100 is too high given `data_confidence_score = 53`.

---

## Action priorities

### P0

1. QCOM missing-FCF support regression.

### P1

2. IONQ archetype false classification.
3. trading-calendar-aware freshness fix.
4. internal_research_quality_score cap calibration.

### P2

5. archetype-specific internal-best rendering for RGTI/QBTS/quantum manual-review cases.

---

## Vega master prompt

```text
MASTER-SPRINT: Manual Focus Guardrail Corrections from Batch 004

Ziel:
Die Manual-Focus-Review aus Batch 004 zeigt vier systemische Probleme. Diese sollen gezielt gehärtet werden. Keine neue große Architektur. Keine Guard-Lockerung. Keine Ticker-Hardcodierung. Keine Report-Polishing-Schleife.

Probleme:
1. QCOM ist passed/Accumulate, obwohl FCF TTM und P/FCF unavailable sind und Data-Ops weiterhin P0 IR/FCF support verlangt.
2. IONQ wird als STANDARD_GROWTH klassifiziert, obwohl es ein quantum/frontier-tech high-valuation negative-FCF Fall ist.
3. PRICE_DATE_BEFORE_AS_OF_DATE feuert bei 2026-05-17 trotz price_basis 2026-05-15, obwohl 2026-05-17 ein Sonntag ist.
4. internal_research_quality_score ist bei IONQ/NVDA/QCOM 100, obwohl Datenvertrauen niedrig/mittel und Manual-Review-Gründe vorhanden sind.

BLOCK 1 — QCOM Missing-FCF Guard Regression

Regel:
Wenn FCF TTM unavailable oder P/FCF unavailable ist und QCOM/Semiconductor AI Infra als Accumulate/Buy durchgehen würde:
- publishable=false oder manual_review, außer OCF/FCF support ist durch current-period IR/SEC evidence belegt.
- external_display_rating = Manual Review / Hold Pending FCF Support.
- Missing FCF darf nicht als positive cash-conversion claim gelten.

Tests:
- QCOM with missing FCF -> not plain Accumulate.
- QCOM with valid current-period FCF/OCF evidence -> Accumulate allowed if other gates pass.
- QCOM display rule remains active.

BLOCK 2 — IONQ Archetype Correction

Regel:
Quantum/frontier-tech firms with real revenue >100M, negative FCF, EV/Sales >50 and SBC/revenue >50 should not default to STANDARD_GROWTH.

Expected:
- IONQ -> EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH or frontier-tech equivalent.
- RGTI/QBTS remain SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL if their metrics fit.
- GOOGL/SNOW/MSFT not affected.

Tests:
- IONQ not STANDARD_GROWTH under current evidence.
- IONQ not clean passed.
- RGTI and QBTS deep-tech regression green.

BLOCK 3 — Trading-Calendar Freshness

Regel:
PRICE_DATE_BEFORE_AS_OF_DATE darf nicht manual_review auslösen, wenn price_basis_date der letzte verfügbare Handelstag vor einem Wochenende/Feiertag ist.

Implementiere:
- latest_trading_day awareness or conservative weekend handling.
- 2026-05-17 with 2026-05-15 close = fresh.

Tests:
- Sunday report date + Friday close -> no stale/manual reason.
- Monday after market close with Friday data when newer close exists -> stale.
- historical_guardrail_test remains allowed.

BLOCK 4 — Internal Research Score Calibration

Regeln:
- If data_confidence_score < 60, internal_research_quality_score cap <= 85.
- If manual_review reasons include true source disagreement, FCF anomaly, period denominator bug, missing earnings date or source frame issues, internal score cap <= 90.
- If internal_best_report is generic template prose for a manual-review archetype, cap <= 85.
- Manual review can still score higher than publish score, but not 100 when evidence is weak.

Tests:
- NVDA data_confidence 53 -> internal score not 100.
- IONQ data_confidence 60 with multiple manual review reasons -> internal score not 100.
- GOOGL/SNOW Gold-v1 unaffected.

BLOCK 5 — Archetype-Specific Internal Best Rendering

For SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL:
- internal_best_report.md should use deep-tech manual-review sections, not generic claim prose.
- Apply to RGTI/QBTS/IONQ only if the archetype fits.

Required sections:
- Statusbox
- Technology Reality Check
- Commercial Adoption
- Contract / Order Materiality
- Financial Reality
- Accounting Quality
- Valuation Disconnect
- Technical Setup as Timing Only
- Final Internal View
- Required Follow-up

BLOCK 6 — Re-run Focus Check

Run:
manual_focus_guardrail_fix_check

Tickers:
IONQ, NVDA, QBTS, QCOM, RGTI

Expected:
- QCOM no longer plain Accumulate if FCF unavailable.
- IONQ no longer STANDARD_GROWTH.
- PRICE_DATE_BEFORE_AS_OF_DATE removed where latest Friday close is fresh for weekend report.
- internal research scores no longer 100 for weak-data manual-review cases.
- RGTI/QBTS remain manual_review.
- Artifact consistency clean.

Akzeptanz:
- pytest grün
- compileall grün
- no guard loosening
- no ticker hardcoding except QCOM display policy already established
- GOOGL/SNOW regression green
```

## Bottom line

Batch 004 is still valuable. It surfaced the right next problems:

- QCOM likely false pass.
- IONQ archetype false negative.
- weekend freshness false manual-review reason.
- internal score overconfidence.

Fix these before trusting the passed/manual split from this batch.
