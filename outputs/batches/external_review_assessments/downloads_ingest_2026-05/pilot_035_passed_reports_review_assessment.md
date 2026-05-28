# Pilot 035 Passed Reports — ChatGPT Quality Review

Bundle reviewed: `chatgpt_passed_review_bundle.zip`
Source batch: `phase12_real_pilot_035_current_ir_claim_semantics`
Tickers reviewed: AAPL, AVGO, GOOGL, META, MSFT, NFLX, SNOW

## Executive Verdict

The pipeline has improved materially versus the previous bundle. The reports now contain real claim objects, evidence mapping, section structure, rating constraints and ticker-specific language. However, the current `passed` label is still too generous for several reports.

**Overall judgment:**

- **Control backbone:** strong.
- **Content layer:** improved, but still too template-driven.
- **Fully publishable reports:** 0/7 if “publishable” means external/institutional quality.
- **Good internal draft candidates:** GOOGL and SNOW.
- **Should be demoted to manual_review:** AVGO.
- **Passed but needs current-period context hardening:** AAPL, META, MSFT, NFLX.

The recurring weakness is no longer missing claims. The new weakness is that many claims are still *semi-substantive*: they contain a metric and a generic interpretation, but not enough current-period, company-specific analysis.

---

## Cross-Report Findings

### 1. Claim substance improved, but many claims remain formulaic

Examples of recurring template phrases:

- “validated revenue scale is …”
- “FCF may be company-defined or period-sensitive …”
- “source-quality issues persist …”
- “DecisionPacket permissions connect fundamental score, technical score and risk score …”

These are safer than hallucinated claims, but they are not yet strong analyst writing. A good report should say *what specifically changed this quarter*, *why it matters*, and *how it affects rating/action*.

### 2. Current-period IR context is still uneven

GOOGL and SNOW are closest to the intended state. AAPL, AVGO, META, MSFT and NFLX still rely too heavily on TTM packet values and generic interpretation.

### 3. Evidence labels in the body are too broad

“SEC filing” and “Company IR release” are not enough for a human reviewer. The body can stay compact, but at least the Current Period section should show:

- source short name,
- period,
- value,
- metric basis,
- whether the value is GAAP, non-GAAP, company-defined or derived.

### 4. Quality Score still over-rewards structure

AAPL gets 90 and NFLX gets 90 despite not having enough current-quarter business context. AVGO gets 87 even though its latest Q1 FY2026 context is materially missing from the report.

A quality score above 90 should require:

- current-period IR/Earnings context,
- sector-specific KPIs,
- current-quarter thesis update,
- final rating rationale that is not merely “DecisionPacket says so.”

### 5. Final Rating section is still too mechanical

The line “the final action should use X because DecisionPacket permissions connect scores to the corridor” is a control statement, not an investment conclusion.

Better pattern:

> “We rate X as Hold because FCF quality and balance sheet support the core thesis, but the stock’s P/FCF and technical extension limit new-money urgency. We would add only on a pullback to validated support or after confirmed acceleration in [current KPI].”

---

## Ticker-by-Ticker Review

## AAPL — Status: Passed, Quality 90, Rating: Accumulate

### Pipeline facts

- Revenue TTM: $444.33B
- FCF TTM: $146.27B
- FCF margin: 32.9%
- EV/Sales: 9.30x
- P/FCF: 28.61x
- RSI: 67.26
- Preferred rating: Accumulate

### External/current-period check

Apple reported fiscal Q2 2026 revenue of $111.2B, diluted EPS of $2.01, best March-quarter revenue, iPhone revenue and EPS records, Services revenue at a record, more than $28B of operating cash flow, and a $100B buyback authorization.

### Assessment

AAPL should not be a clean `Accumulate` report yet. The packet numbers are plausible, but the report misses the current-quarter business story: iPhone 17 demand, Services revenue, gross margin, capital return, AI strategy and regulatory/platform risk. The rating should probably be **Accumulate on pullback / staged Accumulate**, not a simple Accumulate.

### Required fix

Add current-period AAPL KPI claims:

- Q2 FY2026 revenue and EPS,
- iPhone growth / Services record,
- operating cash flow and buyback,
- AI strategy uncertainty,
- regulatory/App Store risk,
- technical extension near RSI 67 and above 200-SMA.

**Publishability:** internal draft only.

---

## AVGO — Status: Passed, Quality 87, Rating: Hold

### Pipeline facts

- Revenue TTM: $65.18B
- FCF TTM: $22.65B
- EV/Sales: 31.90x
- P/FCF: 92.23x
- RSI: 69.28
- Preferred rating: Hold

### External/current-period check

Broadcom reported Q1 FY2026 revenue of $19.311B, Q1 AI revenue of $8.4B (+106% YoY), Q1 FCF of $8.01B, Q2 FY2026 revenue guidance of about $22.0B and Q2 AI semiconductor revenue expectation of $10.7B.

### Assessment

AVGO should not have passed. The report’s TTM revenue appears stale or not current-period adjusted. It does not process Broadcom’s Q1 FY2026 AI revenue, Q2 guidance, custom AI accelerator/networking demand, or VMware/infrastructure-software mix. Given P/FCF above 90x and EV/Sales above 30x, this should be a **valuation/current-period review**, not a clean Hold publish.

### Required fix

- Current Q1 FY2026 IR data must be used.
- AI semiconductor revenue and Q2 guide must appear in the thesis.
- Infrastructure software / VMware mix must be separated from semiconductor AI.
- P/FCF >90 should require either current FCF support or manual_review.

**Publishability:** should be manual_review.

---

## GOOGL — Status: Passed, Quality 95, Rating: Hold

### Pipeline facts

- Revenue TTM: $398.90B
- FCF TTM: $64.43B
- EV/Sales: 11.64x
- P/FCF: 73.78x
- RSI: 81.33
- Preferred rating: Hold

### External/current-period check

Alphabet reported Q1 2026 revenue of $109.9B (+22%), Google Services revenue of $89.6B (+16%), Google Cloud revenue of $20.0B (+63%), operating margin of 36.1%, Other Income gain of $37.7B, Q1 capex of $35.7B and TTM free cash flow of $64.4B.

### Assessment

GOOGL is the best report in the bundle. The rating **Hold** is plausible because fundamentals are strong but RSI is overbought and P/FCF is high. The report now includes Cloud, AI capex and FCF language.

However, it still needs more explicit current-period numerical KPIs in the body. It mentions “Cloud growth” but should state the actual Cloud revenue/growth and capex numbers in the main analysis, not only rely on TTM metrics.

### Required fix

Add an explicit Current Quarter block:

- Q1 revenue $109.9B,
- Google Cloud $20.0B / +63%,
- operating margin 36.1%,
- Q1 capex $35.7B,
- TTM FCF $64.4B,
- Other Income one-off gain $37.7B.

**Publishability:** close; acceptable as internal research draft, not external publish yet.

---

## META — Status: Passed, Quality 92, Rating: Hold

### Pipeline facts

- Revenue TTM: $197.38B
- FCF TTM: $44.34B
- EV/Sales: 7.34x
- P/FCF: 34.99x
- RSI: 39.90
- Preferred rating: Hold

### External/current-period check

Meta reported Q1 2026 revenue of $56.311B (+33%), operating income of $22.872B, operating margin of 41%, net income of $26.773B, a tax benefit affecting EPS, Q1 operating cash flow of $32.226B, Q1 FCF of $12.39B, cash/marketable securities of $81.18B, Q2 revenue guidance of $58–61B and FY2026 capex guidance of $125–145B.

### Assessment

The report has the right broad conclusion: **Hold** is plausible because fundamentals are strong, but chart trend is damaged and AI capex is a major debate. But the report lacks the company-specific META drivers: Family of Apps advertising, Reality Labs, tax benefit, capex guidance and operating cash flow.

### Required fix

Meta-specific current period claims should include:

- Q1 revenue growth and operating margin,
- Q2 revenue guide,
- capex guidance increase,
- Reality Labs loss if available,
- Q1 FCF and tax benefit adjustment.

**Publishability:** internal draft only.

---

## MSFT — Status: Passed, Quality 92, Rating: Hold

### Pipeline facts

- Revenue TTM: $311.90B
- FCF TTM: $67.65B
- EV/Sales: 9.59x
- P/FCF: 45.28x
- RSI: 52.59
- Preferred rating: Hold

### External/current-period check

Microsoft reported FY2026 Q3 revenue of $82.9B (+18%), operating income of $38.4B, net income of $31.8B, Microsoft Cloud revenue of $54.5B (+29%), Intelligent Cloud revenue of $34.7B (+30%), Azure and other cloud services growth of 40%, and AI business annual revenue run rate above $37B.

### Assessment

The Hold rating is plausible. The report correctly recognizes strong fundamentals but a weak technical setup. But it underuses current-period evidence: Azure growth, Microsoft Cloud revenue, AI run-rate and AI capex pressure are the actual investment debate. The report is still too generic for a company this well covered.

### Required fix

Add current-period MSFT claims:

- Microsoft Cloud $54.5B / +29%,
- Azure +40%,
- Intelligent Cloud $34.7B / +30%,
- AI run-rate $37B,
- AI capex / gross-margin pressure.

**Publishability:** internal draft only.

---

## NFLX — Status: Passed, Quality 90, Rating: Hold

### Pipeline facts

- Revenue TTM: $45.38B
- FCF TTM: $12.68B
- EV/Sales: 8.14x
- P/FCF: 29.79x
- RSI: 34.15
- Preferred rating: Hold

### External/current-period check

Netflix Q1 2026 sources report revenue around $12.25B (+16%), operating income around $4.0B, operating margin around 32.3%, free cash flow around $5.1B and some softness in Q2 guidance. Some sources also note a one-time termination-fee effect and resumed buybacks.

### Assessment

The report is directionally okay but not strong. It misses the actual Netflix thesis: ad-tier growth, pricing, content slate, margin guidance, buybacks, password-sharing effects, subscriber/engagement indicators and the effect of non-recurring items on Q1 FCF/net income.

The Hold rating is plausible, but the report should not score 90 without current-quarter Netflix-specific KPI claims.

### Required fix

Add current-period NFLX claims:

- Q1 revenue and operating margin,
- FCF and one-time/non-recurring effects,
- ad-tier / advertiser growth,
- buyback authorization,
- Q2/FY guidance quality.

**Publishability:** internal draft only.

---

## SNOW — Status: Passed, Quality 95, Rating: Tactical Underweight

### Pipeline facts

- Revenue TTM: $4.34B
- Company-defined FCF: $1.12B
- SBC/Revenue: 26.4%
- GAAP operating margin: -34.1%
- EV/Sales: 10.79x
- P/FCF: 42.70x
- RSI: 44.76
- Preferred rating: Tactical Underweight

### External/current-period check

Snowflake reported FY2026 Q4 revenue of $1.28B (+30%), product revenue of $1.23B (+30%), NRR of 125%, 733 customers with >$1M trailing product revenue, RPO of $9.77B (+42%), FY2026 FCF of $1.120B and adjusted FCF of $1.193B.

### Assessment

SNOW is one of the best reports. Tactical Underweight is plausible because the chart is damaged, GAAP profitability is weak, SBC is high and valuation is still meaningful. The company-defined FCF support is now correctly captured.

The report still needs to show Snowflake-specific KPI values directly in the body. It references NRR/RPO/product revenue but often says “do not upgrade without confirmation” rather than stating the confirmed values.

### Required fix

Add explicit Snowflake KPI claims:

- Q4 product revenue $1.23B / +30%,
- FY product revenue $4.472B / +29%,
- NRR 125%,
- RPO $9.77B / +42%,
- 733 customers above $1M,
- FY adjusted FCF $1.193B,
- FY2027 product revenue guide $5.66B / +27%.

**Publishability:** closest to publishable; still needs KPI-value injection into the body.

---

# Overall Rating of the Passed Bundle

| Ticker | Pipeline Status | My Review Status | Main Issue |
|---|---|---|---|
| AAPL | Passed | Internal draft only | Current Q2 context missing; Accumulate too broad |
| AVGO | Passed | Should be manual_review | Q1 FY2026 AI/guidance context missing; stale metrics risk |
| GOOGL | Passed | Best candidate | Needs explicit Q1 KPI values in body |
| META | Passed | Internal draft only | Missing Q1 tax/capex/ads/Reality Labs context |
| MSFT | Passed | Internal draft only | Missing Azure/Cloud/AI-capex specifics |
| NFLX | Passed | Internal draft only | Missing ad-tier/guidance/one-off FCF context |
| SNOW | Passed | Near publishable | Needs exact NRR/RPO/product revenue KPIs in body |

---

# Recommended Next Sprint

## Current-Period KPI Injection + Final Writing Quality Sprint

The system now has enough controls. The bottleneck is the final prose layer: it still writes “validated scale” instead of true current-period investment analysis.

### Tasks

1. **Current-period KPI injection**
   - If current-period IR metrics exist, at least 3 exact KPI values must appear in the main body, not just appendix.
   - Required for AAPL, AVGO, GOOGL, META, MSFT, NFLX, SNOW.

2. **Ticker-specific KPI requirements**
   - AAPL: Q2 revenue, iPhone, Services, OCF, buyback, gross margin, AI/regulatory risk.
   - AVGO: Q1 revenue, AI revenue, Q2 guide, AI semiconductor guide, VMware/software mix, FCF.
   - GOOGL: Q1 revenue, Cloud revenue/growth, operating margin, capex, TTM FCF, Other Income one-off.
   - META: Q1 revenue, operating margin, Q1 FCF, capex guidance, tax benefit, Reality Labs/FoA split if available.
   - MSFT: Microsoft Cloud, Azure, Intelligent Cloud, AI run-rate, capex/gross-margin pressure.
   - NFLX: Q1 revenue, operating margin, FCF, ad-tier, buyback/guidance, non-recurring items.
   - SNOW: Product revenue, NRR, RPO, >$1M customers, FCF/adjusted FCF, FY2027 product revenue guide.

3. **Substantive claim scoring upgrade**
   - A claim is not substantive unless it includes a concrete current-period metric or a sector/ticker KPI.
   - TTM-only claims can count, but only if linked to the rating action.

4. **Quality score tightening**
   - Reports missing current-period KPIs cannot score above 85.
   - Reports with generic final rating rationale cannot score above 88.
   - A score above 92 requires explicit current-quarter KPI discussion.

5. **Decision-language upgrade**
   - Replace “because DecisionPacket permissions connect scores…” with an investment reason.
   - Example: “Hold because Cloud growth and Search cash generation remain strong, but P/FCF and RSI >80 make new money unattractive without a pullback.”

6. **AVGO demotion rule**
   - If latest fiscal quarter IR release exists but is not reflected in current-period claims, status should be manual_review.

---

# Suggested Vega Prompt

```text
Start a Current-Period KPI Injection + Final Writing Quality Sprint.

Goal:
The passed reports from Pilot 035 still read too much like packet-driven templates. They must include current-period, ticker-specific KPI claims in the main body and final rating sections must explain the investment logic, not just cite DecisionPacket permissions.

Do not build new architecture. Harden claim generation, report composer, quality score and dashboard counts.

Tasks:
1. Current-period KPI injection:
   - If current-period IR/Earnings metrics exist, at least 3 exact current-period KPI values must appear in the main body.
   - TTM values alone are not enough for a quality score above 85.

2. Ticker-specific KPI requirements:
   - AAPL: Q2 revenue, iPhone, Services, OCF, buyback, gross margin, AI/regulatory risk.
   - AVGO: Q1 revenue, AI revenue, Q2 guide, AI semiconductor guide, VMware/software mix, FCF.
   - GOOGL: Q1 revenue, Cloud revenue/growth, operating margin, capex, TTM FCF, Other Income one-off.
   - META: Q1 revenue, operating margin, Q1 FCF, capex guidance, tax benefit, Reality Labs/FoA split if available.
   - MSFT: Microsoft Cloud revenue, Azure growth, Intelligent Cloud, AI run-rate, capex/gross-margin pressure.
   - NFLX: Q1 revenue, operating margin, FCF, ad-tier, buyback/guidance, non-recurring items.
   - SNOW: Product revenue, NRR, RPO, >$1M customers, FCF/adjusted FCF, FY2027 product revenue guide.

3. Substantive claim rule:
   - A claim is substantive only if it includes a concrete metric and a company-specific or sector-specific interpretation.
   - Generic claims such as “validated revenue scale” or “source-quality issues persist” do not count unless tied to a real KPI and rating/action implication.

4. Final Rating rewrite:
   - Replace mechanical DecisionPacket language with investment reasoning.
   - Keep DecisionPacket constraints, but explain the rating with actual business/valuation/technical evidence.

5. Quality score tightening:
   - Missing current-period KPI values: cap quality at 85.
   - Generic final rating rationale: cap quality at 88.
   - Score >92 requires current-quarter KPI discussion in main report.

6. AVGO guard:
   - If current Q1 FY2026 IR release exists but report does not reflect Q1 AI revenue, Q2 guide and Q1 FCF, AVGO must be manual_review.

7. Run new pilot:
   - batch_id = phase12_real_pilot_036_kpi_writing_quality
   - same 30 ticker universe
   - source_ingestion_mode
   - create dashboard_status.json, pilot_review.md, chatgpt_passed_review_bundle.zip

Acceptance:
- pytest green
- compileall green
- no failed batch aborts
- GOOGL and SNOW should remain passed if KPI injection works
- AVGO should pass only if current Q1 FY2026 KPI context is present
- AAPL/META/MSFT/NFLX should either include current KPI claims or score below 85/manual_review
- final rating sections must no longer rely mainly on “DecisionPacket permissions connect scores” language
```

---

# Bottom Line

Pilot 035 is a major improvement, but the passed reports are still not final-grade. The system has moved from “empty skeletons” to “evidence-backed drafts.” The next leap is from “evidence-backed draft” to “actual investment research.”

GOOGL and SNOW are the best candidates to push across the line first. AVGO is the clearest false pass. AAPL, META, MSFT and NFLX need current-period KPI injection before I would trust them as publishable internal research.
