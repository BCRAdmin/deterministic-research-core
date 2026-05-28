# Current Batch 002 — Publish Bundle Review

## Scope

Reviewed bundle: `chatgpt_publish_review_bundle.zip`
Source batch: `phase12_current_batch_002`
Price basis date: `2026-05-08`
Contained passed reports: `AAPL`, `CRM`, `DDOG`, `GOOGL`, `META`, `MSFT`, `NFLX`, `SNOW`.

Manual-review tickers shown in dashboard but not bundled: `AVGO`, `MU`, `NVDA`, `QCOM`.

## Executive Verdict

This is a usable pilot baseline. The bundle is meaningfully better than the earlier skeleton and claim-ledger outputs. The publish reports are readable, have current-period KPIs in the main body, avoid obvious internal pipeline language, and keep evidence in the appendix.

However, I would not treat all 8 passed reports as equally strong. The bundle should be interpreted as:

- **Gold-v1 / strongest:** `GOOGL`, `SNOW`
- **Good internal drafts:** `MSFT`, `AAPL`, `META`, `NFLX`, `DDOG`
- **Needs caution despite passed:** `CRM`

The main issues are now editorial/analytical and a few residual consistency checks, not backbone architecture.

## Batch Health

From `pilot_review.md`:

- Passed: `8`
- Manual review: `4`
- Failed: `0`
- Average quality score: `87.0`
- Median quality score: `90.0`
- Lowest quality score: `74.0`
- True source disagreements: `136`
- Earnings date unavailable: `12`

The external display-policy fix worked: `QCOM` is externally shown as `Hold Pending FCF Support` rather than a clean Accumulate.

## Global Findings

### What Works Now

- `publish_report.md` exists for each bundled ticker.
- Main bodies are largely free of internal pipeline language.
- Current-period KPIs appear in the main body.
- Evidence IDs are kept in the appendix.
- Ratings generally read like analyst judgments rather than DecisionPacket output.
- Manual-review tickers are excluded from the publish bundle.

### Remaining Cross-Cutting Weaknesses

1. **Valuation is still shallow.**
   EV/Sales and P/FCF are named, but there is still limited peer context, little sensitivity modeling, and limited reverse-expectations framing.

2. **Action triggers remain qualitative.**
   Many action plans say “wait for proof” or “add on pullback,” but not enough specific price, KPI, margin, FCF, or earnings triggers are quantified.

3. **EarningsCalendar coverage remains weak.**
   `EARNINGS_DATE_UNAVAILABLE` appears for all 12 tickers. This is acceptable for pilot mode, but not for unattended production.

4. **Some appendix claims still contain data limitations or generic internal phrasing.**
   This is acceptable in the appendix, but the system should eventually clean the appendix too for external use.

5. **CRM has too many reconciliation disagreements for Gold status.**
   It passed, but with `25` true source disagreements. That should cap it as an internal draft, not a publish-grade report.

## Ticker Reviews

### GOOGL — Gold-v1 Confirmed

**Pipeline rating:** Hold
**Quality:** 95

GOOGL remains the strongest Mega-Cap / Ads / Cloud template. The report uses current-period KPIs, balances Cloud growth and AI capex pressure, and frames Hold plausibly. It is suitable as a Gold-v1 internal template.

**What works:**

- Current-period KPIs are in the main body.
- Hold is justified by strong fundamentals versus valuation/timing risk.
- Evidence structure is clean.

**Remaining improvements:**

- Add a stronger valuation sensitivity paragraph.
- Make rating-change triggers more measurable.

**Verdict:** Keep as Gold-v1.

---

### SNOW — Gold-v1 Confirmed, but Watch Rating Consistency

**Pipeline rating:** Hold in dashboard; report language still references Tactical Underweight logic.
**Quality:** 95

SNOW is the strongest SaaS / Consumption / Data Platform template. The report includes product revenue, NRR, RPO, adjusted FCF, SBC/Revenue, and technical weakness.

**What works:**

- Strong company-specific KPI usage.
- Good treatment of consumption growth versus SBC/valuation risk.
- Evidence remains in appendix.

**Issue to fix:**

The final section begins with `Final Rating: Hold` but says “Tactical Underweight fits...” in the same paragraph. This is an internal inconsistency. If the external rating is Hold, the prose should say “Hold with a tactical underweight bias” or “Hold, but underweight relative to target allocation.” If the intended rating is Tactical Underweight, the dashboard/Decision layer should align.

**Verdict:** Gold-v1, but fix rating wording consistency.

---

### MSFT — Good Near-Gold Candidate

**Pipeline rating:** Hold
**Quality:** 90

MSFT is now a credible Mega-Cap / Cloud / AI Infrastructure report. It includes Q3 revenue, Microsoft Cloud, Azure growth, AI run-rate, and capex/FCF conversion framing.

**What works:**

- Clear cloud/AI thesis.
- Hold is logical: strong business, weak technical score / capex conversion uncertainty.
- Final rating section is much better than earlier versions.

**Remaining improvements:**

- Add a sharper valuation paragraph.
- Add more concrete upgrade/downgrade triggers.
- Better distinguish Azure demand from AI capex margin pressure.

**Verdict:** Good internal draft; near-Gold after valuation/action-plan polish.

---

### AAPL — Good Draft, Accumulate Is Still Slightly Broad

**Pipeline rating:** Accumulate
**Quality:** 90

AAPL’s report is readable and company-specific. It uses revenue, EPS, operating cash flow and buyback authorization well.

**What works:**

- Strong Apple-specific capital-return framing.
- Accumulate is staged rather than aggressive.
- Risk section includes product-cycle, AI and regulatory issues.

**Concern:**

The Accumulate rating is plausible only if it is explicitly pullback/staging based. The text does say staged accumulation, but external readers may still interpret Accumulate as a direct buy. The action plan should make “not at any price” more prominent.

**Verdict:** Good internal draft; keep Accumulate only with staged-entry language.

---

### META — Good Draft, But CapEx/AI ROI Debate Needs More Depth

**Pipeline rating:** Hold
**Quality:** 90

META’s report is materially improved. It includes Q1 revenue, operating margin, FCF and FY2026 capex guidance.

**What works:**

- Strong current-period financial framing.
- Hold is plausible because AI capex creates risk/reward tension.
- No obvious internal systems language.

**Remaining improvements:**

- Reality Labs / Family of Apps split should be more explicit if data is available.
- AI infrastructure ROI should be a deeper central debate, not just a risk mention.
- Tax/one-off effects should be separated from recurring earnings if material.

**Verdict:** Good internal draft; not Gold yet.

---

### NFLX — Good Draft, Needs More Netflix-Specific Operating Drivers

**Pipeline rating:** Hold
**Quality:** 90

NFLX is readable and has current-period revenue, operating income, margin and FCF.

**What works:**

- Good profitability and FCF framing.
- Hold rating is reasonable because valuation/content-cycle risks remain.
- Evidence is kept in appendix.

**Remaining improvements:**

- Needs more ad-tier, engagement, content-cost and guidance specificity.
- Action triggers should include ad-tier monetization, engagement, and FCF durability.

**Verdict:** Good internal draft, but still less company-specific than GOOGL/SNOW.

---

### DDOG — Much Improved SaaS Draft, Valuation Risk Is Correctly Prominent

**Pipeline rating:** Hold
**Quality:** 92

DDOG is much better after IR reconciliation. It now uses FY2025 revenue, operating cash flow, company-defined FCF, SBC and cash/marketable securities in the main thesis.

**What works:**

- Current-period IR values are in the main body.
- SBC and valuation pressure are properly treated.
- Hold is logical: high-quality business, valuation/SBC discipline required.

**Concern:**

P/FCF around 100x is a significant valuation risk. A clean Hold is okay, but the report should be explicit that upside depends on revenue durability and FCF/SBC improvement.

**Verdict:** Good internal SaaS draft; not Gold yet.

---

### CRM — Passed, But Keep Below Gold Due to Reconciliation Noise

**Pipeline rating:** Hold
**Quality:** 88

CRM now includes FY2026 revenue, OCF, FCF, SBC and cash/marketable securities. That is a major improvement.

**What works:**

- Current-period IR framing is much better.
- Hold is logical: strong cash generation, AI/Data Cloud growth proof still needed.
- No hard claim/evidence issue in the main report.

**Concerns:**

- Dashboard shows `25` true source disagreements.
- Evidence appendix still has a line implying company-defined FCF is “not available in evidence set,” while the main report states company-defined FCF of `$14.4B`. This should be reconciled in the appendix or evidence mapping.

**Verdict:** Acceptable internal draft, but not Gold; keep flagged for reconciliation-watch.

## Manual Review Tickers

Manual review remains appropriate for:

- `AVGO`
- `MU`
- `NVDA`
- `QCOM`

This is a healthy state. Do not force them green.

## Recommendations

### Immediate Small Fixes

1. Fix SNOW rating wording inconsistency: Hold vs Tactical Underweight.
2. Fix CRM appendix/evidence wording around company-defined FCF.
3. Keep QCOM external display policy as currently implemented.
4. Keep AVGO/MU/NVDA/QCOM in manual_review unless specific issues are resolved.

### Operational Next Step

Freeze this as a workable Current Batch baseline and begin using the system in pilot mode:

- Passed reports can be used as internal drafts.
- Manual-review reports require human review.
- Any Echtgeld-relevant report should still be externally reviewed.
- Run 5D/10D/20D outcome checks as soon as windows mature.

## Final Assessment

This is the strongest overall bundle so far. It is not unattended-production-ready, but it is ready for controlled pilot use.

**Pilot mode: yes.**
**Unattended publishing: no.**
**Continue architecture build: no.**
**Next focus: outcome review + selective manual report review.**
