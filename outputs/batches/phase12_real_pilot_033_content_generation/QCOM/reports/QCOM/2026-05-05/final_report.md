# QCOM Research Report
## Executive Summary
- **QCOM_CLAIM_001**: QCOM enters the report with a validated Accumulate rating corridor and a price basis frozen before interpretation.
  Investment implication: The committee text should stay inside the Accumulate action frame.
  Evidence IDs: `QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05`.

## Data / Source Quality Note
- Report as-of date: `2026-05-05`.
- Price basis: `2026-05-05` close via `csv_price_provider`.
- Validation issues in packet: `1`.
- True unresolved source disagreements: `25`.

## Validated Metric Table
| Metric | Value |
|---|---:|
| Close | 186.55 |
| 50 SMA | 138.13 |
| 200 SMA | 156.96 |
| RSI 14 | 78.32 |
| FCF TTM | Metric unavailable in validated packet. |
| SBC / Revenue | 6.8% |
| EV / Sales | 4.26 |
| P / FCF | Metric unavailable in validated packet. |

## Business & Segment Context
Business context is intentionally grounded in validated financial scale, cash generation, balance-sheet and source-quality claims. Segment-specific interpretation should only be expanded when validated segment evidence is available.

## Fundamental Analysis
- **QCOM_CLAIM_002**: Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion.
  Counterargument: Revenue scale alone does not prove attractive returns or valuation discipline.
  Investment implication: Use revenue evidence as context, not as a standalone buy signal.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061`.
- **QCOM_CLAIM_003**: Free cash flow is a central quality check and should be interpreted only from the validated packet value.
  Counterargument: FCF may be company-defined or period-sensitive and can require reconciliation review.
  Investment implication: FCF quality supports the thesis only if no sanity guard blocks the report.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW`.
- **QCOM_CLAIM_004**: Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation.
  Counterargument: High-growth software companies may tolerate higher SBC while scaling.
  Investment implication: Treat SBC as a risk modifier rather than an automatic rating override.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_SBC_TO_REVENUE, QCOM_SEC_DERIVED_SBC_TO_REVENUE`.
- **QCOM_CLAIM_005**: Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims.
  Investment implication: A stronger liquidity position can widen the acceptable holding corridor.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_CASH, QCOM_SEC_COMPANYFACTS_804328_CASH_AND_EQUIVALENTS, QCOM_SEC_COMPANYFACTS_804328_CASH_AND_INVESTMENTS, QCOM_SEC_COMPANYFACTS_804328_NET_CASH, QCOM_SEC_cash_and_equivalents_FY2025_FY_0000804328-25-000085, QCOM_SEC_cash_and_equivalents_FY2026_Q1_0000804328-26-000017, QCOM_SEC_cash_and_equivalents_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_DEBT, QCOM_SEC_COMPANYFACTS_804328_NET_DEBT, QCOM_SEC_COMPANYFACTS_804328_TOTAL_DEBT`.

## Valuation / Multiples
- **QCOM_CLAIM_006**: Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples.
  Counterargument: Packet-derived valuation can still be blocked by sanity guards when source reconciliation is suspect.
  Investment implication: Do not upgrade rating solely from valuation language if audit has financial-sanity errors.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05`.
- **QCOM_CLAIM_007**: P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings.
  Investment implication: The rating should stay conservative when multiples are expensive or flagged.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061`.

## Technical Setup
- **QCOM_CLAIM_008**: The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation.
  Investment implication: Timing language should follow the validated technical trend state.
  Evidence IDs: `QCOM_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05`.
- **QCOM_CLAIM_009**: Moving-average structure and momentum should guide whether the action is immediate, staged or defensive.
  Counterargument: Technical weakness can be temporary if fundamentals and catalysts improve.
  Investment implication: Use staged entries or trims when technical and fundamental signals diverge.
  Evidence IDs: `QCOM_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05`.

## Bull Case
- **QCOM_CLAIM_010**: The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor.
  Counterargument: Strong scale does not resolve valuation or reconciliation anomalies.
  Investment implication: Bullish language must remain bounded by DecisionPacket permissions.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW`.
- **QCOM_CLAIM_011**: A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative.
  Investment implication: Add or accumulate language should require confirmation when the preferred rating is not Buy.
  Evidence IDs: `QCOM_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05`.

## Bear Case
- **QCOM_CLAIM_012**: The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings.
  Investment implication: Manual review remains appropriate when financial-sanity guards fire.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_SBC_TO_REVENUE, QCOM_SEC_DERIVED_SBC_TO_REVENUE`.
- **QCOM_CLAIM_013**: Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit.
  Investment implication: Avoid blocked Sell language when the DecisionPacket allows only trim or hold actions.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW`.

## Key Risks
- **QCOM_CLAIM_014**: Validation and audit issues are part of the research view and can override otherwise clean narrative sections.
  Investment implication: Blocking audit errors should keep the report in manual review.
  Evidence IDs: `QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05`.
- **QCOM_CLAIM_015**: Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible.
  Investment implication: Source-quality limitations belong in the final action plan.
  Evidence IDs: `QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW`.

## Catalysts & Triggers
- **QCOM_CLAIM_016**: Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims.
  Investment implication: If earnings are unavailable, the report should state that limitation rather than inventing timing.
  Evidence IDs: `QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05`.
- **QCOM_CLAIM_017**: Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet.
  Investment implication: Use confirmation language instead of hard price targets unless risk/reward levels are validated.
  Evidence IDs: `QCOM_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05`.

- Earnings date unavailable in validated packet; no earnings event-risk claim is made.

## Scenario View
- Base case: use `Accumulate` as the committee anchor.
- Bull case: move only within the allowed rating corridor if validated fundamentals and technical confirmation improve.
- Bear case: downgrade only within the allowed rating corridor unless new validated blocking evidence appears.

## Final Rating & Action Plan
Final Rating: Accumulate

Allowed ratings: Buy, Accumulate, Hold. Blocked ratings: Strong Buy, Tactical Trim, Tactical Underweight, Underweight, Sell, Avoid.

Primary action: Staged accumulation.
Initial position: 20-30%.

- **QCOM_CLAIM_018**: The final action should use Accumulate, because the DecisionPacket identifies it as the preferred rating within the allowed corridor.
  Counterargument: Another allowed rating may be defensible, but blocked ratings are not allowed.
  Investment implication: Final report wording must choose Accumulate or another allowed rating with explicit justification.
  Evidence IDs: `QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05`.

## Evidence Appendix
| Claim ID | Claim | Evidence IDs | Source Type | Confidence | Metric Refs |
|---|---|---|---|---|---|
| QCOM_CLAIM_001 | QCOM enters the report with a validated Accumulate rating corridor and a price basis frozen before interpretation. | QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| QCOM_CLAIM_002 | Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion. | QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061 | sec_filing | high | revenue_ttm |
| QCOM_CLAIM_003 | Free cash flow is a central quality check and should be interpreted only from the validated packet value. | QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW | sec_filing | high | free_cash_flow_ttm |
| QCOM_CLAIM_004 | Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation. | QCOM_SEC_COMPANYFACTS_804328_SBC_TO_REVENUE, QCOM_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | sbc_to_revenue |
| QCOM_CLAIM_005 | Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims. | QCOM_SEC_COMPANYFACTS_804328_CASH, QCOM_SEC_COMPANYFACTS_804328_CASH_AND_EQUIVALENTS, QCOM_SEC_COMPANYFACTS_804328_CASH_AND_INVESTMENTS, QCOM_SEC_COMPANYFACTS_804328_NET_CASH, QCOM_SEC_cash_and_equivalents_FY2025_FY_0000804328-25-000085, QCOM_SEC_cash_and_equivalents_FY2026_Q1_0000804328-26-000017, QCOM_SEC_cash_and_equivalents_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_DEBT, QCOM_SEC_COMPANYFACTS_804328_NET_DEBT, QCOM_SEC_COMPANYFACTS_804328_TOTAL_DEBT | sec_filing | medium | net_cash, total_debt |
| QCOM_CLAIM_006 | Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples. | QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv, sec_filing | medium | revenue_ttm, free_cash_flow_ttm, close |
| QCOM_CLAIM_007 | P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings. | QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061 | sec_filing | medium | free_cash_flow_ttm, revenue_ttm |
| QCOM_CLAIM_008 | The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation. | QCOM_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | technical_indicators, close |
| QCOM_CLAIM_009 | Moving-average structure and momentum should guide whether the action is immediate, staged or defensive. | QCOM_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| QCOM_CLAIM_010 | The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor. | QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| QCOM_CLAIM_011 | A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative. | QCOM_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| QCOM_CLAIM_012 | The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings. | QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_SBC_TO_REVENUE, QCOM_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | free_cash_flow_ttm, sbc_to_revenue |
| QCOM_CLAIM_013 | Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit. | QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| QCOM_CLAIM_014 | Validation and audit issues are part of the research view and can override otherwise clean narrative sections. | QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| QCOM_CLAIM_015 | Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible. | QCOM_SEC_COMPANYFACTS_804328_REVENUE, QCOM_SEC_COMPANYFACTS_804328_REVENUE_TTM, QCOM_SEC_COMPANYFACTS_804328_SALES, QCOM_SEC_COMPANYFACTS_804328_UMSATZ, QCOM_SEC_revenue_FY2025_FY_0000804328-25-000085, QCOM_SEC_revenue_FY2025_Q3_0000804328-25-000045, QCOM_SEC_revenue_FY2026_Q1_0000804328-26-000017, QCOM_SEC_revenue_FY2026_Q2_0000804328-26-000061, QCOM_SEC_COMPANYFACTS_804328_CASHFLOW, QCOM_SEC_COMPANYFACTS_804328_FCF, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW, QCOM_SEC_COMPANYFACTS_804328_FREE_CASH_FLOW_TTM, QCOM_SEC_COMPANYFACTS_804328_FREE_CASHFLOW | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| QCOM_CLAIM_016 | Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims. | QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| QCOM_CLAIM_017 | Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet. | QCOM_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| QCOM_CLAIM_018 | The final action should use Accumulate, because the DecisionPacket identifies it as the preferred rating within the allowed corridor. | QCOM_YAHOO_CHART_PRICE_CSV_CLOSE, QCOM_YAHOO_CHART_PRICE_CSV_OHLCV, QCOM_YAHOO_CHART_PRICE_CSV_PRICE, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, QCOM_YAHOO_CHART_PRICE_CSV_PRICE_DATA, QCOM_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
