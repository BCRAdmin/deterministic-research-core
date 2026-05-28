# ChatGPT Review — Phase 12 / Pilot 033 Claim Reports

## Executive Summary

The five reviewed reports are **no longer empty skeletons**: they contain 18 analyst-claim objects each, Evidence IDs, a validated metric table, a decision packet, and an evidence appendix. That is a real improvement over the prior bundle.

However, the reports are still **not publishable as investment research**. They are mostly **meta-claims about the pipeline** rather than company-specific analysis. The wording is repeated across DDOG, QCOM, GOOGL, SNOW, and CRM. The reports say things like “Revenue scale is available in the validated packet” instead of making a substantive claim such as “Datadog grew FY2025 revenue 28% to $3.43B while FCF margin reached ~27%, but valuation at ~68x P/FCF leaves little margin of safety.”

The control stack is strong. The content layer is active, but still template-driven. The next work should be a **Claim Substance Sprint**, not another control-system phase.

---

## Overall Findings

| Area | Status | Assessment |
|---|---|---|
| Content completeness | Improved | Reports now have required sections and 18 claims. |
| Evidence mapping | Strong mechanically | Claims have Evidence IDs, but often too many IDs and not enough human-readable source context. |
| Claim substance | Weak | Claims are generic and often identical across companies. |
| Company-specific interpretation | Weak | Segment drivers, guidance, product dynamics, and competitive context are mostly missing. |
| Data sanity | Mixed | GOOGL/SNOW look more plausible; DDOG/CRM have major official-vs-packet gaps; QCOM lacks FCF and guidance but still gets Accumulate. |
| Rating discipline | Mechanically strong | Blocked ratings are respected. |
| Human publishability | Not yet | Suitable as internal control output, not final research. |

---

## Key Systemic Problems

### 1. Claims are evidence-mapped but not analytical enough

The current claims often prove that data exists, not what it means.

Current style:

> Revenue scale is available in the validated packet and should anchor business-quality discussion.

Needed style:

> Datadog’s FY2025 revenue grew 28% and FCF was $915M, but the stock’s high P/FCF multiple makes the setup more suitable for Hold than Buy unless growth or margin guidance improves.

### 2. Quality Score over-rewards structural completeness

Reports with generic repeated claims receive scores around 97–99. This is too high. A content score should distinguish:

- section exists
- claim exists
- claim has evidence
- claim is company-specific
- claim contains actual investment interpretation
- claim supports the final rating

Currently the system mostly checks the first three.

### 3. Evidence IDs are too verbose

Each claim often lists many evidence IDs. That is useful for machine traceability but bad for human review.

Needed:

- short human-facing citation label, e.g. `DDOG FY2025 Earnings Release`, `SEC 10-K FY2025`, `CSV OHLCV 2026-05-05`
- full Evidence IDs only in appendix or JSON

### 4. Sector-specific language is missing

QCOM uses software/SaaS language such as “High-growth software companies may tolerate higher SBC.” That is inappropriate for a semiconductor company.

The claim generator needs sector-aware templates:

- Semiconductors: inventory, cyclicality, QCT/QTL mix, handset exposure, automotive/IoT, gross margin, buybacks, guidance.
- SaaS: NRR, RPO, ARR, FCF margin, SBC, GAAP/non-GAAP gap.
- Mega-cap ads/cloud: capex, cloud margin, ad growth, AI monetization, regulatory risk.

### 5. Some packet metrics still conflict with official figures

The most important cases:

- DDOG official FY2025 revenue and FCF are higher than the packet values.
- CRM official FY2026 revenue and FCF are higher than the packet values.
- QCOM has FCF unavailable and guidance missing despite a recent Q2 FY2026 release.

These should not necessarily block every report, but they should reduce confidence and prevent a top-tier quality score.

---

## Per-Ticker Review

## DDOG

**System rating:** Hold
**Quality score:** 99
**Human review:** Not publishable yet

### What works

- Hold is directionally reasonable.
- Technical setup is captured: price above 200-SMA, RSI near 70, positive MACD.
- Valuation risk is recognized through high P/FCF.
- Evidence mapping exists.

### Main problems

- The packet reports DDOG revenue TTM of $3.164B and FCF TTM of $784M. Datadog’s FY2025 release reported revenue of $3.43B, operating cash flow of $1.05B and FCF of $915M. The packet appears to miss the full-year company-defined values or under-aggregate current-period data.
- Cash/investments appears materially understated in the packet: DDOG reported cash, cash equivalents and marketable securities of $4.47B, while the packet shows ~$401M.
- The report’s actual claims are generic and do not discuss Datadog’s product/AI observability narrative, large customer growth, 603 $1M+ ARR customers, or 2026 guidance.

### Revised judgment

**Hold / Watchlist.**
Not publishable until company-defined FY2025 revenue, FCF and cash/investments are reconciled. The report should say: strong SaaS execution and FCF, but valuation and SBC keep it from Buy.

---

## QCOM

**System rating:** Accumulate
**Quality score:** 97
**Human review:** Not publishable; rating too aggressive

### What works

- FY2025 revenue around $44.2B is close to Qualcomm’s reported FY2025 revenue of $44.3B.
- EV/Sales around 4.3x is plausible.
- The Accumulate rating is at least within the allowed corridor.

### Main problems

- FCF is unavailable in the validated packet, yet the report still uses a constructive Accumulate frame. For a mature semiconductor company, missing FCF should reduce conviction.
- Technical setup looks overextended: RSI 78.3 and price far above the 50-SMA. Accumulate should probably require a pullback or post-guidance confirmation.
- Qualcomm announced Q2 FY2026 results on April 29, 2026 with $10.6B revenue and Q3 FY2026 guidance of $9.2B–$10.0B; the report does not incorporate this current guidance.
- The report contains software-specific language about SBC tolerance, which is inappropriate for QCOM.

### Revised judgment

**Hold / Accumulate only on pullback.**
Do not publish as a straight Accumulate while FCF and current guidance are missing and RSI is overbought.

---

## GOOGL

**System rating:** Hold
**Quality score:** 98
**Human review:** Best of the five, but still too generic

### What works

- The packet FCF TTM around $64.9B aligns closely with Alphabet’s reported TTM FCF around $64.4B from Q1 2026 materials.
- Revenue TTM around $343.8B is directionally plausible.
- Hold is reasonable given strong fundamentals but very overbought technicals: RSI above 81.
- Source disagreements are low.

### Main problems

- The report does not analyze the actual Q1 2026 story: $109.9B quarterly revenue, 63% Cloud growth, $20B Cloud revenue, 36.1% operating margin, and material unrealized investment gains.
- It misses the capex/AI infrastructure debate, which is one of the main current Alphabet investment issues.
- Hold may be too mild; with RSI >81 and strong post-earnings move, “Hold / Tactical Trim” might be more consistent than plain Hold for new money.

### Revised judgment

**Hold / Tactical Trim for overextended positions.**
This is the most technically acceptable report in the bundle, but it still reads like a template instead of an Alphabet analysis.

---

## SNOW

**System rating:** Tactical Underweight
**Quality score:** 98
**Human review:** Directionally plausible, but still generic

### What works

- Tactical Underweight is plausible: price below both 50-SMA and 200-SMA, weak technical score, negative GAAP net income, high SBC/revenue.
- FCF TTM around $1.15B is close to Snowflake’s reported FY2026 FCF of $1.12B / adjusted FCF of $1.19B.
- SBC/revenue around 30% correctly flags dilution/profitability quality concerns.

### Main problems

- The report does not discuss Snowflake’s actual FY2026 facts: Q4 revenue $1.28B, product revenue $1.23B, NRR 125%, RPO $9.77B, and FY2027 product revenue outlook.
- It treats SBC as a general warning but does not distinguish GAAP loss, non-GAAP operating income, FCF, adjusted FCF, and SBC-driven dilution economics.
- Tactical Underweight should include explicit review triggers: reclaim 50-SMA, product revenue acceleration, FCF margin stability, SBC reduction, or guidance beat.

### Revised judgment

**Tactical Underweight / Hold core only.**
Mechanically plausible, but not publishable until it includes company-specific Snowflake drivers.

---

## CRM

**System rating:** Hold
**Quality score:** 97
**Human review:** Not publishable due metric gaps and generic content

### What works

- Hold is plausible given CRM’s strong cash generation and weak technical structure below 200-SMA.
- EV/Sales around 4.2x and P/FCF around 16.5x look directionally reasonable if the packet values are accepted.
- SBC/revenue around 8% is plausible and not alarming.

### Main problems

- Salesforce FY2026 official release reported revenue of $41.5B, operating cash flow of $15.0B and FCF of $14.4B. The packet shows revenue $39.77B and FCF $10.86B, materially lower.
- The report does not analyze Salesforce-specific issues: Agentforce, Data 360, RPO/cRPO, Informatica contribution, margin targets, buybacks/dividend, or FY2027 guidance.
- True source disagreements are 25, but quality score remains 97. That is too generous.

### Revised judgment

**Hold / Manual review until FY2026 company-defined FCF is reconciled.**
The rating may be fine, but the report should not be publishable with those gaps.

---

## System Fix Recommendations

### 1. Add a Substantive Claim Gate

A claim should not pass just because it has evidence. It must contain either:

- a validated metric value,
- a company-specific business driver,
- a sector-specific interpretation,
- a direct implication for rating/action.

Generic claims like “Revenue scale is available” should not count toward analyst_claim_count.

### 2. Add a Company-Specific Claim Coverage Gate

Each report should include at least:

- 2 company-specific business drivers,
- 1 current earnings/guidance driver when available,
- 1 valuation implication using actual multiples,
- 1 technical setup interpretation with actual levels,
- 1 rating/action rationale tied to allowed ratings.

### 3. Add Current Reporting Period Priority

For as-of 2026-05-05, the reports should prefer the most recent company IR release over stale or partially aggregated SEC facts when company-defined FCF/revenue/guidance is available.

### 4. Make Missing FCF Rating-Sensitive

If FCF is missing:

- mature profitable company: downgrade conviction by 1 level,
- high-growth SaaS: allow report only if OCF/FCF alternative source exists,
- no Accumulate/Buy unless valuation can be supported by another validated cashflow or earnings metric.

### 5. Add Sector-Aware Claim Templates

Do not use SaaS language for QCOM. Do not use generic capex language for all firms. Route claim generation by sector/business model.

### 6. Evidence Display Should Be Human-Friendly

Main report should show short source labels. Full Evidence IDs should remain in appendix or JSON.

### 7. Quality Score Needs a Substance Component

Current score is too high. Add:

- Generic-claim penalty,
- repeated-template penalty,
- missing company-specific-driver penalty,
- missing current-guidance penalty when available,
- source disagreement penalty based on current-period relevance.

---

## Recommended Vega Prompt

```text
Implement a Claim Substance and Current-Period Hardening Sprint.

Goal:
The reports now have analyst claims, but many are generic meta-claims. Improve the content layer so only company-specific, evidence-backed analytical claims count toward publishability.

Tasks:
1. Substantive Claim Gate:
   - A claim counts only if it contains at least one of:
     validated metric value, company-specific business driver, sector-specific interpretation, rating/action implication.
   - Generic claims such as "Revenue scale is available" do not count.
   - analyst_claim_count_for_publishability should use substantive claims only.

2. Repeated Template Penalty:
   - Detect claims repeated across tickers with only ticker/evidence changed.
   - If >50% of claims match generic templates, cap content_score at 60.

3. Company-Specific Coverage Gate:
   - Require at least 2 company-specific business-driver claims.
   - Require 1 current earnings/guidance claim if IR source exists.
   - Require 1 valuation claim using actual validated multiples.
   - Require 1 technical claim using actual levels.
   - Require 1 final rating rationale tied to DecisionPacket.

4. Current Period Data Priority:
   - If company IR reports current-year revenue/FCF/guidance, prefer company-defined IR values over derived SEC TTM values.
   - Specifically retest DDOG and CRM official FY values.

5. Missing FCF Rating Rule:
   - If FCF unavailable and rating is Accumulate/Buy, require either validated earnings/OCF support or downgrade to Hold/Manual Review.
   - Retest QCOM.

6. Sector-Aware Claim Templates:
   - SaaS: ARR/RPO/NRR/SBC/FCF/GAAP-vs-non-GAAP.
   - Semis: revenue segments, cycle, inventory, QCT/QTL, guidance, buybacks, gross margin.
   - Mega-cap Ads/Cloud: ad growth, cloud growth/margin, capex, AI monetization, regulatory risk.

7. Human-Friendly Evidence:
   - In main report, show short source labels.
   - Keep full Evidence IDs in appendix only.

Acceptance:
- pytest and compileall green.
- DDOG and CRM should not be publishable until current FY revenue/FCF reconcile with company IR.
- QCOM Accumulate should downgrade or manual_review if FCF/guidance remains missing and RSI is overbought.
- GOOGL and SNOW can remain publishable if company-specific claims are added.
- Quality Score should fall for generic template reports.
```

---

## Bottom Line

The pipeline has moved from **empty skeletons** to **evidence-mapped claim skeletons**. That is a real improvement.

But the reports are still not true investment research. The next task is not more validation infrastructure; it is **substantive, company-specific claim generation** backed by the strong evidence system you already built.
