# SNOW Research Report
## Executive Summary
- **SNOW_CLAIM_001**: SNOW enters the report with a validated Tactical Underweight rating corridor and a price basis frozen before interpretation.
  Investment implication: The committee text should stay inside the Tactical Underweight action frame.
  Evidence IDs: `SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05`.

## Data / Source Quality Note
- Report as-of date: `2026-05-05`.
- Price basis: `2026-05-05` close via `csv_price_provider`.
- Validation issues in packet: `1`.
- True unresolved source disagreements: `1`.

## Validated Metric Table
| Metric | Value |
|---|---:|
| Close | 141.71 |
| 50 SMA | 157.05 |
| 200 SMA | 206.40 |
| RSI 14 | 44.76 |
| FCF TTM | 1,153,756,000 |
| SBC / Revenue | 30.1% |
| EV / Sales | 10.79 |
| P / FCF | 41.45 |

## Business & Segment Context
Business context is intentionally grounded in validated financial scale, cash generation, balance-sheet and source-quality claims. Segment-specific interpretation should only be expanded when validated segment evidence is available.

## Fundamental Analysis
- **SNOW_CLAIM_002**: Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion.
  Counterargument: Revenue scale alone does not prove attractive returns or valuation discipline.
  Investment implication: Use revenue evidence as context, not as a standalone buy signal.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211`.
- **SNOW_CLAIM_003**: Free cash flow is a central quality check and should be interpreted only from the validated packet value.
  Counterargument: FCF may be company-defined or period-sensitive and can require reconciliation review.
  Investment implication: FCF quality supports the thesis only if no sanity guard blocks the report.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **SNOW_CLAIM_004**: Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation.
  Counterargument: High-growth software companies may tolerate higher SBC while scaling.
  Investment implication: Treat SBC as a risk modifier rather than an automatic rating override.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_SBC_TO_REVENUE, SNOW_SEC_DERIVED_SBC_TO_REVENUE`.
- **SNOW_CLAIM_005**: Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims.
  Investment implication: A stronger liquidity position can widen the acceptable holding corridor.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_CASH, SNOW_SEC_COMPANYFACTS_1640147_CASH_AND_EQUIVALENTS, SNOW_SEC_COMPANYFACTS_1640147_CASH_AND_INVESTMENTS, SNOW_SEC_COMPANYFACTS_1640147_NET_CASH, SNOW_SEC_cash_and_equivalents_FY2026_FY_0001640147-26-000008, SNOW_SEC_cash_and_equivalents_FY2026_Q2_0001640147-25-000187, SNOW_SEC_cash_and_equivalents_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_DEBT, SNOW_SEC_COMPANYFACTS_1640147_NET_DEBT, SNOW_SEC_COMPANYFACTS_1640147_TOTAL_DEBT`.

## Valuation / Multiples
- **SNOW_CLAIM_006**: Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples.
  Counterargument: Packet-derived valuation can still be blocked by sanity guards when source reconciliation is suspect.
  Investment implication: Do not upgrade rating solely from valuation language if audit has financial-sanity errors.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05`.
- **SNOW_CLAIM_007**: P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings.
  Investment implication: The rating should stay conservative when multiples are expensive or flagged.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211`.

## Technical Setup
- **SNOW_CLAIM_008**: The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation.
  Investment implication: Timing language should follow the validated technical trend state.
  Evidence IDs: `SNOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05`.
- **SNOW_CLAIM_009**: Moving-average structure and momentum should guide whether the action is immediate, staged or defensive.
  Counterargument: Technical weakness can be temporary if fundamentals and catalysts improve.
  Investment implication: Use staged entries or trims when technical and fundamental signals diverge.
  Evidence IDs: `SNOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05`.

## Bull Case
- **SNOW_CLAIM_010**: The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor.
  Counterargument: Strong scale does not resolve valuation or reconciliation anomalies.
  Investment implication: Bullish language must remain bounded by DecisionPacket permissions.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **SNOW_CLAIM_011**: A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative.
  Investment implication: Add or accumulate language should require confirmation when the preferred rating is not Buy.
  Evidence IDs: `SNOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05`.

## Bear Case
- **SNOW_CLAIM_012**: The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings.
  Investment implication: Manual review remains appropriate when financial-sanity guards fire.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_SBC_TO_REVENUE, SNOW_SEC_DERIVED_SBC_TO_REVENUE`.
- **SNOW_CLAIM_013**: Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit.
  Investment implication: Avoid blocked Sell language when the DecisionPacket allows only trim or hold actions.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Key Risks
- **SNOW_CLAIM_014**: Validation and audit issues are part of the research view and can override otherwise clean narrative sections.
  Investment implication: Blocking audit errors should keep the report in manual review.
  Evidence IDs: `SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05`.
- **SNOW_CLAIM_015**: Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible.
  Investment implication: Source-quality limitations belong in the final action plan.
  Evidence IDs: `SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Catalysts & Triggers
- **SNOW_CLAIM_016**: Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims.
  Investment implication: If earnings are unavailable, the report should state that limitation rather than inventing timing.
  Evidence IDs: `SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05`.
- **SNOW_CLAIM_017**: Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet.
  Investment implication: Use confirmation language instead of hard price targets unless risk/reward levels are validated.
  Evidence IDs: `SNOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05`.

- Earnings date unavailable in validated packet; no earnings event-risk claim is made.

## Scenario View
- Base case: use `Tactical Underweight` as the committee anchor.
- Bull case: move only within the allowed rating corridor if validated fundamentals and technical confirmation improve.
- Bear case: downgrade only within the allowed rating corridor unless new validated blocking evidence appears.

## Final Rating & Action Plan
Final Rating: Tactical Underweight

Allowed ratings: Hold, Tactical Trim, Tactical Underweight. Blocked ratings: Strong Buy, Buy, Accumulate, Underweight, Sell, Avoid.

Primary action: Temporarily stay below target exposure.
Trim sizing: 20-30%.

- **SNOW_CLAIM_018**: The final action should use Tactical Underweight, because the DecisionPacket identifies it as the preferred rating within the allowed corridor.
  Counterargument: Another allowed rating may be defensible, but blocked ratings are not allowed.
  Investment implication: Final report wording must choose Tactical Underweight or another allowed rating with explicit justification.
  Evidence IDs: `SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05`.

## Evidence Appendix
| Claim ID | Claim | Evidence IDs | Source Type | Confidence | Metric Refs |
|---|---|---|---|---|---|
| SNOW_CLAIM_001 | SNOW enters the report with a validated Tactical Underweight rating corridor and a price basis frozen before interpretation. | SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| SNOW_CLAIM_002 | Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion. | SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211 | sec_filing | high | revenue_ttm |
| SNOW_CLAIM_003 | Free cash flow is a central quality check and should be interpreted only from the validated packet value. | SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | high | free_cash_flow_ttm |
| SNOW_CLAIM_004 | Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation. | SNOW_SEC_COMPANYFACTS_1640147_SBC_TO_REVENUE, SNOW_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | sbc_to_revenue |
| SNOW_CLAIM_005 | Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims. | SNOW_SEC_COMPANYFACTS_1640147_CASH, SNOW_SEC_COMPANYFACTS_1640147_CASH_AND_EQUIVALENTS, SNOW_SEC_COMPANYFACTS_1640147_CASH_AND_INVESTMENTS, SNOW_SEC_COMPANYFACTS_1640147_NET_CASH, SNOW_SEC_cash_and_equivalents_FY2026_FY_0001640147-26-000008, SNOW_SEC_cash_and_equivalents_FY2026_Q2_0001640147-25-000187, SNOW_SEC_cash_and_equivalents_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_DEBT, SNOW_SEC_COMPANYFACTS_1640147_NET_DEBT, SNOW_SEC_COMPANYFACTS_1640147_TOTAL_DEBT | sec_filing | medium | net_cash, total_debt |
| SNOW_CLAIM_006 | Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples. | SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv, sec_filing | medium | revenue_ttm, free_cash_flow_ttm, close |
| SNOW_CLAIM_007 | P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings. | SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211 | sec_filing | medium | free_cash_flow_ttm, revenue_ttm |
| SNOW_CLAIM_008 | The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation. | SNOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | technical_indicators, close |
| SNOW_CLAIM_009 | Moving-average structure and momentum should guide whether the action is immediate, staged or defensive. | SNOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| SNOW_CLAIM_010 | The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor. | SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| SNOW_CLAIM_011 | A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative. | SNOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| SNOW_CLAIM_012 | The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings. | SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_SBC_TO_REVENUE, SNOW_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | free_cash_flow_ttm, sbc_to_revenue |
| SNOW_CLAIM_013 | Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit. | SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| SNOW_CLAIM_014 | Validation and audit issues are part of the research view and can override otherwise clean narrative sections. | SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| SNOW_CLAIM_015 | Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible. | SNOW_SEC_COMPANYFACTS_1640147_REVENUE, SNOW_SEC_COMPANYFACTS_1640147_REVENUE_TTM, SNOW_SEC_COMPANYFACTS_1640147_SALES, SNOW_SEC_COMPANYFACTS_1640147_UMSATZ, SNOW_SEC_revenue_FY2026_FY_0001640147-26-000008, SNOW_SEC_revenue_FY2026_Q2_0001640147-25-000187, SNOW_SEC_revenue_FY2026_Q3_0001640147-25-000211, SNOW_SEC_COMPANYFACTS_1640147_CASHFLOW, SNOW_SEC_COMPANYFACTS_1640147_FCF, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASH_FLOW_TTM, SNOW_SEC_COMPANYFACTS_1640147_FREE_CASHFLOW, SNOW_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| SNOW_CLAIM_016 | Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims. | SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| SNOW_CLAIM_017 | Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet. | SNOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| SNOW_CLAIM_018 | The final action should use Tactical Underweight, because the DecisionPacket identifies it as the preferred rating within the allowed corridor. | SNOW_YAHOO_CHART_PRICE_CSV_CLOSE, SNOW_YAHOO_CHART_PRICE_CSV_OHLCV, SNOW_YAHOO_CHART_PRICE_CSV_PRICE, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, SNOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, SNOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
