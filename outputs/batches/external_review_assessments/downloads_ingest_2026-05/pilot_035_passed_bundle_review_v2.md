# Pilot 035 Passed-Bundle Review — ChatGPT Assessment

## Scope

Reviewed uploaded bundle: `chatgpt_passed_review_bundle.zip`.

Observed bundle contents:

- `AAPL`
- `AVGO`
- `GOOGL`
- `META`
- `MSFT`
- `NFLX`
- `SNOW`

Important mismatch: the prior project summary said the bundle should contain only GOOGL and SNOW, but this uploaded ZIP contains 7 passed reports from `phase12_real_pilot_035_current_ir_claim_semantics`.

## Executive Verdict

The pipeline is now far stronger than the initial skeleton stage, but the current passed reports are still **internal-draft quality**, not final publishable investment research.

The two best candidates remain:

1. `GOOGL`
2. `SNOW`

However, even these still need writing-quality and current-period-KPI improvements before they can be treated as final-grade reports.

The biggest hard problem is no longer numerical validation. The biggest problem is that the reports still read like a structured claim ledger rather than a human-quality equity research note.

## Cross-Report Findings

### 1. Mechanical rating language is still present

Despite the dashboard indicating `mechanical_rating_language_count = 0`, multiple final reports still contain language like:

> "The final action should use Hold, because DecisionPacket permissions connect [ticker]'s fundamental score, technical score and risk score to that allowed rating corridor."

This appears in final rating sections, including GOOGL, SNOW, AVGO, AAPL and others.

This should be counted as mechanical rating language and should block final-grade publishability or cap quality.

### 2. Current-period KPI injection is still incomplete

The reports often mention the right categories, but not the actual current-period values in the main body.

Examples:

- GOOGL mentions Cloud and capex themes, but the main body should explicitly show Q1 revenue, Cloud revenue/growth, operating margin, Other Income one-off, Q1 CapEx and FCF.
- SNOW mentions product revenue, NRR and RPO, but the main body does not consistently show the actual Product Revenue, RPO, NRR and customer-count values.
- AVGO mentions AI/datacenter mix, but does not explicitly process Q1 FY2026 AI revenue, Q2 guidance and Q1 FCF in the main report.
- AAPL, META, MSFT and NFLX remain too generic relative to their current-period earnings context.

### 3. Evidence-backed does not yet equal analyst-grade

The reports now have Evidence IDs and validated claims, but many claims are still not deep enough:

- They often state that a metric is validated.
- They often say a rating is constrained by the DecisionPacket.
- They often use generic company labels such as "platform scale", "ecosystem monetization", or "capex intensity".

A final research report should convert those into investment judgments:

- Why is the metric important?
- Is it improving or deteriorating?
- Is it above or below expectations?
- What risk does it create?
- Why does it justify the specific rating?

### 4. Evidence appendix is too heavy for the main reading flow

The Evidence Appendix is useful for audit, but the main report still feels too close to the claim/evidence model. Human-facing reports should be more concise and narrative, with full IDs hidden in the appendix.

### 5. Quality score still overstates writing quality

Quality scores such as 95 for GOOGL/SNOW are too high if the final rating section still contains mechanical DecisionPacket language and if current-period KPIs are not fully surfaced in the main report.

Suggested interpretation:

- 90–95 should require real current-period KPI discussion and a human-readable rating thesis.
- 80–89 should be internal-draft quality.
- Below 80 should be manual-review or internal-only.

## Ticker-by-Ticker Review

### AAPL

**Pipeline rating:** Accumulate
**Quality score:** 90
**My verdict:** Internal draft; not final-grade publishable.

Strengths:

- Core financial metrics are present.
- Rating corridor and action plan are consistent with the packet.
- Evidence mapping exists.

Issues:

- Accumulate is too broad given the report does not properly process current-quarter Apple-specific drivers.
- The main text does not sufficiently discuss Services, iPhone performance, buybacks, EPS, operating cash flow, China/regulatory risk or AI strategy in a concrete way.
- The report still uses generic language like "mega-cap platform growth" and "AI/cloud investment".
- Final rating rationale remains mechanical.

Recommended status: **Manual review or internal draft**, unless current-quarter Apple KPI claims are strengthened.

### AVGO

**Pipeline rating:** Hold
**Quality score:** 87
**My verdict:** False pass / manual review.

Strengths:

- The report correctly notices valuation discipline with EV/Sales and P/FCF.
- Hold is more conservative than Buy.

Issues:

- AVGO-specific current-period context is still missing from the main report.
- Q1 FY2026 AI revenue, Q2 revenue guidance and Q1 FCF should be explicit in the report.
- The report still uses generic phrases like "cycle recovery" and "AI/datacenter mix" without enough current-period numerical support.
- P/FCF above 90 and EV/Sales above 30 should require a stronger valuation-risk explanation.

Recommended status: **Manual review** until Q1 AI revenue, Q2 guide, Q1 FCF and VMware/software mix are explicitly processed.

### GOOGL

**Pipeline rating:** Hold
**Quality score:** 95
**My verdict:** Best candidate, but still internal-draft rather than final-grade.

Strengths:

- Hold is plausible: strong Q1 fundamentals but overbought technical setup and high capex/valuation tension.
- Current-period FCF is correct enough and company-defined FCF is used.
- Key themes are right: Search, YouTube, Google Cloud, AI monetization, capex intensity.

Issues:

- The main report should explicitly include Q1 revenue, Google Cloud revenue/growth, operating margin, Other Income one-off, CapEx and FCF in the analytical sections.
- The final rating section still says the action follows DecisionPacket permissions, which is not acceptable final-grade investment writing.
- Some claims remain meta-claims about validated data rather than investment analysis.

Recommended status: **Strong internal draft / near publishable after writing rewrite.**

### META

**Pipeline rating:** Hold
**Quality score:** 92
**My verdict:** Internal draft.

Strengths:

- Hold is plausible.
- Data appears broadly supported.
- Capex/AI risk language is present at a high level.

Issues:

- The report needs concrete Q1 META KPIs in the main body: revenue, operating margin, FCF, CapEx guidance, Reality Labs if available, tax benefit if material.
- The report still feels generic and does not fully separate advertising cash-engine strength from AI capex risk.
- Final rating text remains too mechanical.

Recommended status: **Internal draft; not publishable yet.**

### MSFT

**Pipeline rating:** Hold
**Quality score:** 92
**My verdict:** Internal draft.

Strengths:

- Hold is reasonable if technical setup is weak while fundamentals are strong.
- Core TTM metrics are available.

Issues:

- Current Microsoft Cloud, Azure, Intelligent Cloud, commercial RPO and AI run-rate figures should be in the main body.
- The report should explicitly frame the central debate: cloud/AI demand strength vs AI capex/gross-margin pressure.
- The current report uses packet and score language too heavily.

Recommended status: **Internal draft; needs current-quarter Microsoft-specific KPI injection.**

### NFLX

**Pipeline rating:** Hold
**Quality score:** 90
**My verdict:** Internal draft; sector language still wrong/generic.

Strengths:

- Hold is not obviously wrong.
- FCF and operating margin context are available.

Issues:

- The report uses generic mega-cap/platform/cloud language that does not fit Netflix well.
- It should discuss streaming-specific drivers: revenue, operating income, margin, FCF, ad-tier growth, engagement, content spend, buybacks and guidance quality.
- The final rating is still framed mechanically.

Recommended status: **Manual review or internal draft until Netflix-specific content is improved.**

### SNOW

**Pipeline rating:** Tactical Underweight
**Quality score:** 95
**My verdict:** Best with GOOGL; near publishable after KPI values and narrative rewrite.

Strengths:

- Tactical Underweight is directionally plausible because the chart is weak, valuation is not cheap, SBC is high and GAAP losses remain relevant despite strong FCF.
- Company-defined FCF is now used correctly.
- The report mentions the right Snowflake concepts: product revenue, NRR, RPO, customers > $1M, AI Data Cloud, consumption growth.

Issues:

- The main body does not show enough actual Snowflake-specific KPI values such as Product Revenue, RPO, NRR and $1M customer count.
- The report is still too claim-template-like.
- The final rating section still uses DecisionPacket language.

Recommended status: **Strong internal draft / near publishable after KPI and writing rewrite.**

## Overall Publishability Verdict

| Ticker | Current Pipeline Status | ChatGPT Verdict |
|---|---|---|
| AAPL | Passed | Internal draft, Accumulate too broad |
| AVGO | Passed | False pass / manual review |
| GOOGL | Passed | Best candidate, near publishable after rewrite |
| META | Passed | Internal draft |
| MSFT | Passed | Internal draft |
| NFLX | Passed | Internal draft, sector language too generic |
| SNOW | Passed | Best candidate, near publishable after rewrite |

Final-grade publishable: **0/7**
Strong internal drafts: **GOOGL, SNOW**
False pass: **AVGO**

## Required Next Sprint

### Sprint Name

**Final Report Narrative + KPI Value Enforcement Sprint**

### Goals

1. Remove all DecisionPacket/meta language from main report.
2. Require explicit current-period KPI values in main sections.
3. Make final rating rationale human-readable and investment-driven.
4. Make ticker-specific KPI templates value-bearing, not just topic-bearing.
5. Push AVGO back to manual review unless Q1 AI revenue, Q2 guidance and Q1 FCF are explicitly in the main report.
6. Lower quality score when a report is structurally complete but still reads like a claim ledger.

## Proposed Vega Prompt

```text
Starte den Sprint: Final Report Narrative + KPI Value Enforcement.

Ziel:
Die passed Reports aus Pilot 035 sind evidence-backed, aber noch zu mechanisch und nicht final-grade. Entferne DecisionPacket-/scorebasierte Sprache aus dem Hauptreport und erzwinge echte current-period KPI-Werte im Haupttext.

Ausgangslage:
- Bundle aus Pilot 035 enthält AAPL, AVGO, GOOGL, META, MSFT, NFLX, SNOW.
- ChatGPT Review: 0/7 final-grade publishable.
- GOOGL und SNOW sind beste interne Drafts.
- AVGO ist false pass.
- Mechanical rating language ist trotz Count=0 noch im Report vorhanden.

Aufgaben:

1. Mechanische Rating-Sprache blockieren
   - Im Hauptreport verboten:
     "DecisionPacket permissions"
     "allowed rating corridor"
     "fundamental score, technical score and risk score"
     "validated rating corridor"
     "unconstrained model preference"
   - Diese Sprache darf höchstens im internal appendix vorkommen, nicht in Executive Summary, Investment Thesis oder Final Rating.
   - mechanical_rating_language_count muss solche Formulierungen zuverlässig zählen.
   - Wenn mechanical language im Final Rating erscheint: manual_review oder Quality Cap <= 80.

2. Final Rating Abschnitt umschreiben
   Pflichtstruktur:
   - Final Rating
   - Why this rating?
   - Why not more bullish?
   - Why not more bearish?
   - What would change the rating?
   - Action plan

   Der Text muss auf fundamentaler, Bewertungs-, technischer und Risiko-Logik beruhen, nicht auf DecisionPacket-Metadaten.

3. Current-period KPI values must appear in main report
   - KPI themes alone do not count.
   - "Cloud growth" is insufficient.
   - Must write actual value and period, e.g. "Google Cloud revenue rose 63% to $20.0B in Q1 2026."

4. Ticker-specific enforcement
   GOOGL main report must include:
   - Q1 revenue
   - Google Cloud revenue/growth
   - operating margin
   - Q1 CapEx
   - TTM or Q1 FCF
   - one-off Other Income / unrealized gains if available

   SNOW main report must include:
   - Product revenue
   - RPO
   - NRR
   - customers > $1M product revenue
   - company-defined FCF / adjusted FCF
   - SBC or GAAP/Non-GAAP gap

   AVGO main report must include or block:
   - Q1 FY2026 revenue
   - AI revenue
   - Q2 revenue guidance
   - Q1 FCF
   - VMware/software mix
   If missing: AVGO manual_review.

   MSFT main report must include:
   - Microsoft Cloud revenue/growth
   - Azure growth
   - Intelligent Cloud revenue
   - AI run-rate if available
   - capex/margin pressure

   META main report must include:
   - Q1 revenue
   - operating margin
   - FCF
   - CapEx guidance
   - tax/one-off impact if material

   AAPL main report must include:
   - latest quarter revenue
   - EPS
   - Services/iPhone performance
   - operating cash flow
   - buyback authorization

   NFLX main report must include:
   - latest quarter revenue
   - operating income
   - operating margin
   - FCF
   - ad-tier/engagement/guidance if available

5. Quality scoring
   - Quality >90 requires no mechanical rating language and at least 4 explicit current-period KPI values in main report.
   - Quality >92 requires at least one ticker-specific KPI paragraph and a non-mechanical final rating rationale.
   - Reports with correct data but claim-ledger style should cap at 85.

6. Re-run pilot:
   - batch_id = phase12_real_pilot_037_final_narrative_kpi_values
   - same 30 tickers
   - source_ingestion_mode
   - create chatgpt_passed_review_bundle.zip

Acceptance:
- pytest green
- compileall green
- AVGO not passed unless Q1 AI revenue, Q2 guidance and Q1 FCF are in main report
- mechanical_rating_language_count catches DecisionPacket language
- GOOGL and SNOW reports contain actual KPI values in main report
- final rating sections contain human investment logic, not score/permission logic
```

## Bottom Line

The system is very close. The remaining gap is not validation architecture. It is final-writing quality:

- convert claims into prose,
- surface current-period KPI values,
- remove internal decision-system language,
- make final rating rationale sound like an analyst, not a rules engine.
