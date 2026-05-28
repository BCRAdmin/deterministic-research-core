# ChatGPT Review — Passed Reports Bundle (Pilot 034)

## Bundle reviewed

Selected tickers in `chatgpt_passed_review_bundle.zip`:

- AMZN
- AVGO
- GOOGL
- META
- MSFT
- PANW
- SNOW

## Executive judgement

The pipeline has improved materially versus the prior skeleton-report bundle. Reports now contain evidence-mapped claims, sections, action plans, and appendices. However, **the reports are still not consistently publishable as investment research**. The core control stack is strong, but the content layer and current-period metric reconciliation still need tightening.

The biggest issue is not missing sections anymore; the issue is that several reports are **technically complete but analytically shallow**, and some still contain **hard metric problems** that should block publishability.

## Overall status

| Area | Assessment |
|---|---|
| File completeness | Good |
| Evidence attachment | Good mechanically |
| Report structure | Good |
| Claim count | Adequate |
| Claim substance | Improved but still template-heavy |
| Rating discipline | Mostly acceptable, except AMZN and possibly AVGO/PANW |
| Financial metric correctness | Mixed; AMZN is a hard fail |
| Current-period context | Weak in most reports |
| Publishability | 2 candidates close; 5 need manual review or hardening |

## Ticker-level verdicts

| Ticker | Pipeline rating | My verdict | Main reason |
|---|---|---|---|
| AMZN | Accumulate | **Not publishable** | FCF TTM is materially wrong; Accumulate is not defensible with this packet. |
| AVGO | Hold | **Manual review** | EV/Sales and P/FCF are extreme; FCF appears under-reconciled vs current IR/TTM context. |
| GOOGL | Hold | **Closest to publishable** | Metrics are broadly plausible, but report misses key Q1 AI/cloud/capex/one-off gain analysis. |
| META | Hold | **Needs content hardening** | Data broadly plausible; report fails to analyze capex guidance, tax benefit and AI spend risk. |
| MSFT | Hold | **Needs content hardening** | Data broadly plausible; report misses Q3 cloud/AI/capex/current earnings context. |
| PANW | Hold | **Manual review** | FCF unavailable despite company guidance/FCF-margin context; cybersecurity report too generic. |
| SNOW | Hold | **Near-publishable with edits** | Mechanically plausible, but should use company-defined FCF and analyze product revenue, NRR, RPO, FY outlook. |

---

# Key findings

## 1. AMZN should not be passed

AMZN report states:

- FCF TTM: **$104.495B**
- P/FCF: **28.47x**
- Rating: **Accumulate**

This is a hard failure. Amazon's Q1 2026 release and 10-Q state that free cash flow for the trailing twelve months ended March 31, 2026 was **$1.232B**, with operating cash flow of **$148.531B** and property/equipment purchases of **$147.299B**. The report appears to be treating a derived or incompatible cash-flow figure as FCF.

### Required fix

- Company-defined FCF must override SEC-derived FCF when the issuer provides an explicit FCF reconciliation.
- If derived FCF differs from company-defined FCF by more than 10%, block report.
- AMZN should move to manual_review until FCF is corrected.
- Rating corridor should not allow `Accumulate` when FCF is materially wrong and RSI is >80.

Suggested issue code:

```text
COMPANY_DEFINED_FCF_MISMATCH
```

---

## 2. AVGO should not be clean passed without stronger valuation review

AVGO report states:

- EV/Sales: **31.90x**
- P/FCF: **92.23x**
- FCF TTM: **$22.649B**
- Rating: **Hold**

The report correctly has a `GUARD_THRESHOLD_REVIEW`, but still passes. Broadcom reported FY2025 free cash flow of **$26.9B** and Q1 FY2026 free cash flow of **$8.010B**. A simple current TTM approximation using FY2025 plus Q1 FY2026 minus Q1 FY2025 points to a higher FCF than the report's $22.649B. The valuation can still be expensive, but the FCF basis needs explicit reconciliation.

### Required fix

- Treat EV/Sales >30 for semiconductors as publishable only if current IR metrics are reconciled.
- Add current quarter AI revenue / infrastructure software context before allowing publishable Hold.
- For AVGO, report should explain whether valuation reflects post-split price/share-count correctly.

---

## 3. GOOGL is the best report, but still too generic

GOOGL report has plausible headline packet metrics:

- Revenue TTM: **$398.904B**
- FCF TTM: **$63.125B**
- RSI: **81.33**
- Rating: **Hold**

This is directionally plausible. Alphabet's Q1 2026 release reported $109.9B quarterly revenue, 63% Google Cloud growth to $20.0B, operating margin of 36.1%, and other income including a $37.7B net gain primarily from non-marketable equity securities.

### Weakness

The report says GOOGL should reflect Search, YouTube, Google Cloud, AI monetization and capex intensity, but it does not actually analyze:

- Google Cloud +63% growth
- AI/cloud backlog and capacity constraint
- Q1 capex of $35.7B
- TTM FCF pressure vs capex
- unrealized investment gains in net income
- RSI >81 / overbought technical setup

### My rating judgement

Pipeline `Hold` is acceptable. But the report should not be A-/92 unless it includes current-quarter analysis.

---

## 4. META data is broadly plausible but content is weak

META report metrics appear broadly plausible, and Meta's Q1 2026 release supports a strong current-period setup:

- Q1 revenue: **$56.311B**
- Q1 operating income: **$22.872B**
- Q1 FCF: **$12.386B**
- Cash + marketable securities: **$81.18B**
- Capex guidance increased to **$125–145B**

The bundle's TTM revenue and FCF appear directionally plausible.

### Weakness

The report should discuss:

- Q1 tax benefit and EPS quality
- increased capex guidance
- Reality Labs drag
- ad business resilience
- AI infrastructure ROI risk
- technical weakness vs moving averages

Current text is too generic for publishability.

---

## 5. MSFT data is plausible but current-quarter analysis is missing

Microsoft Q3 FY2026 release reported:

- Revenue: **$82.886B**
- Operating income: **$38.398B**
- Net income: **$31.778B**
- Operating cash flow: **$46.679B**
- 9M operating cash flow: **$127.494B**
- 9M capex: **$80.146B**

The packet's TTM revenue and FCF appear plausible, but the report misses the actual current-quarter drivers:

- Microsoft Cloud and Azure growth
- AI capex / gross margin pressure
- OpenAI investment impact
- technical setup: close above 50-SMA but below 200-SMA

Pipeline Hold is plausible, but the write-up needs current-period substance.

---

## 6. PANW should not pass if FCF is unavailable

PANW report states:

- FCF TTM: unavailable
- P/FCF: unavailable
- EV/Sales: **13.41x**
- Rating: Hold

Palo Alto Networks' fiscal 2026 guidance includes adjusted free cash flow margin of **37%**, and Q2 FY2026 revenue grew 15% to $2.6B. If current FCF cannot be reconciled, the report may still be Hold, but it should be passed with limitation or manual_review, not clean publishable.

### Required fix

- For mature cybersecurity/software companies, if FCF is unavailable but company reports/guides FCF margin, require IR current-period FCF or adjusted FCF evidence.
- Do not count a claim saying `FCF unavailable` as a substantive analyst claim.

---

## 7. SNOW is a reasonable candidate, but still needs IR-defined FCF and business KPI analysis

SNOW report states:

- Revenue TTM: **$4.342B**
- FCF TTM: **$992M**
- SBC/Revenue: **26.4%**
- EV/Sales: **10.79x**
- P/FCF: **48.21x**
- Rating: Hold

Snowflake's FY2026 release reported full-year product revenue of **$4.472B**, FCF of **$1.120B**, adjusted FCF of **$1.193B**, NRR of **125%**, RPO of **$9.77B**, and 733 customers with TTM product revenue >$1M.

The packet is close enough to be directionally useful, but report quality would improve if it used company-defined FCF and product revenue rather than generic revenue.

### My rating judgement

Hold is plausible. This is the closest report to a usable internal draft after GOOGL.

---

# Cross-report issues

## A. Reports are still too template-like

Repeated phrase pattern:

```text
[Company] enters the report with a validated [rating] corridor at a frozen close of [price]; the action should reflect [sector phrase] and the current technical setup.
```

This is better than skeleton, but still not a true analyst executive summary.

### Required fix

Executive Summary should include:

- one sentence on current-period fundamentals
- one sentence on valuation
- one sentence on technical setup
- one sentence on why final rating is constrained
- one sentence on what would change the rating

## B. Claims are evidence-mapped but not always analytically meaningful

Example:

```text
Validated FCF TTM is not available in validated packet, making cash conversion a direct rating input.
```

This should not count as a substantive claim. It is a data availability note.

### Required fix

If metric unavailable:

- count as `data_limitation_claim`
- not `substantive_analyst_claim`
- may reduce quality score depending on metric importance

## C. Current-period earnings context is weak

Nearly every report has `earnings_unavailable_count = 1`. For mega-cap tech and software, current earnings are essential.

### Required fix

A report can be publishable only if at least one of the following is true:

- current earnings date is confirmed and current-period earnings are processed
- company has no recent earnings within lookback window
- report clearly states current earnings unavailable and lowers quality score

## D. Current period reconciliation summaries still show stale historical disagreements

AMZN/PANW/MSFT show unresolved disagreements from old years like FY2012/FY2015. These should not influence current-period publishability except as data-quality notes.

### Required fix

Separate:

```text
current_period_true_disagreements
historical_true_disagreements
```

Only current-period unresolved disagreements should affect publishability materially.

## E. Quality scores are still too flat

All selected reports score 92. This is not credible. AMZN has a hard FCF miss and still scores 92.

### Required fix

Quality Score needs heavier penalties:

- company-defined FCF mismatch: block / quality <=60
- missing FCF for FCF-relevant software/cybersecurity: -10 to -20
- no current earnings context: -5 to -15
- template-heavy executive summary: -5
- metric unavailable counted as claim: -5

---

# Recommended next sprint

## Sprint name

`Current-Period IR + Claim Semantics Hardening`

## Goals

1. Company-defined FCF overrides SEC-derived FCF.
2. Current earnings/IR context is mandatory for publishable reports.
3. Metric-unavailable claims do not count as substantive claims.
4. Quality score differentiates good reports from weak reports.
5. Current-period disagreements are separated from historical disagreements.

## Acceptance criteria

```text
AMZN must not pass until FCF TTM = official company-defined FCF.
PANW must not pass if FCF remains unavailable and no IR adjusted FCF support exists.
GOOGL can pass if Q1 cloud/capex/gain context appears in report.
SNOW can pass if product revenue, NRR, RPO and company-defined FCF appear.
Reports with identical template executive summaries lose quality points.
Quality score variance across 7-report bundle should be meaningful, not all 92.
```

---

# Vega prompt

```text
Starte einen gezielten Sprint: Current-Period IR + Claim Semantics Hardening.

Ziel:
Die passed Reports aus phase12_real_pilot_034 sind formal vollständig, aber mehrere sind noch nicht publishable. AMZN hat einen harten FCF-Fehler, PANW hat FCF unavailable, und viele Reports sind zu templatehaft. Fixe nicht durch Abschalten von Guards, sondern durch bessere current-period IR-Priorisierung, Claim-Semantik und Quality-Scoring.

Aufgaben:

1. Company-defined FCF Priority
- Wenn IR/Earnings Release oder 10-Q eine explizite FCF-Reconciliation liefert, muss diese company-defined FCF den SEC-derived FCF-Wert überschreiben.
- Wenn SEC-derived FCF und company-defined FCF um mehr als 10% abweichen:
  Issue = COMPANY_DEFINED_FCF_MISMATCH
  status = manual_review
- AMZN muss diesen Guard triggern, solange FCF TTM im Report nicht dem offiziellen company-defined TTM-FCF entspricht.

2. Metric-unavailable Claim Semantics
- Claims wie "FCF is not available in validated packet" zählen nicht als substantive analyst claims.
- Sie zählen als data_limitation_claim.
- Wenn FCF unavailable bei Software/Cybersecurity/SaaS und Rating nicht klar konservativ ist:
  status = manual_review oder quality penalty.
- PANW darf nicht clean publishable sein, solange FCF unavailable bleibt und keine IR adjusted FCF evidence vorhanden ist.

3. Current Earnings Context Gate
- Für Reports mit recent earnings within last 120 days oder confirmed current period source:
  final_report.md muss mindestens 2 current-period earnings claims enthalten.
- Beispiele:
  revenue growth, segment growth, FCF, capex/guidance, operating margin, one-off gains.
- Wenn current-period IR exists but report lacks current-period claims:
  Issue = MISSING_CURRENT_PERIOD_EARNINGS_CONTEXT

4. Company-specific KPI Coverage
- Mega-cap ads/cloud: require at least 2 of Search/Ads, Cloud, Capex, FCF, operating margin, one-off gains.
- SaaS/Software: require at least 2 of product revenue, NRR/retention, RPO/backlog, ARR, FCF, SBC.
- Semiconductors: require at least 2 of AI revenue, segment revenue, gross margin, FCF, guidance, inventory/cycle.
- Cybersecurity: require at least 2 of ARR/RPO/billings, platformization, FCF/FCF margin, NGS ARR, guidance.

5. Current vs Historical Disagreement Split
- Reconciliation report must separate:
  current_period_true_disagreements
  historical_true_disagreements
- Historical disagreements older than 3 fiscal years should not materially penalize publishability unless they affect current metrics.

6. Quality Score Reweighting
- COMPANY_DEFINED_FCF_MISMATCH: blocking or quality <=60
- MISSING_CURRENT_PERIOD_EARNINGS_CONTEXT: -10 to -20
- metric-unavailable used as substantive claim: -10
- template-heavy executive summary: -5
- no sector KPI coverage: -10
- historical-only disagreements: low/no penalty

7. Re-run 7-report passed-review bundle or pilot subset:
Tickers: AMZN, AVGO, GOOGL, META, MSFT, PANW, SNOW.

Expected:
- AMZN manual_review until FCF corrected.
- PANW manual_review or lower quality until FCF/IR adjusted FCF support exists.
- GOOGL can pass if current Q1 cloud/capex/gain context is included.
- SNOW can pass if product revenue/NRR/RPO/company-defined FCF context is included.
- Quality scores should no longer all cluster at 92.

Acceptance:
- pytest grün
- compileall grün
- no data_bug
- no hard_claim_without_evidence
- no unsupported guidance claims
- no unsupported earnings event claims
- final_report.md reports become less template-like and contain current-period, ticker-specific analysis.
```
