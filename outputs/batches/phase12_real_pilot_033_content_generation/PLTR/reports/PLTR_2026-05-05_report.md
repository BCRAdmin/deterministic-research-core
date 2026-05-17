# PLTR Research Report
## Executive Summary
- **PLTR_CLAIM_001**: PLTR enters the report with a validated Hold rating corridor and a price basis frozen before interpretation.
  Investment implication: The committee text should stay inside the Hold action frame.
  Evidence IDs: `PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05`.

## Data / Source Quality Note
- Report as-of date: `2026-05-05`.
- Price basis: `2026-05-05` close via `csv_price_provider`.
- Validation issues in packet: `1`.
- True unresolved source disagreements: `1`.

## Validated Metric Table
| Metric | Value |
|---|---:|
| Close | 135.91 |
| 50 SMA | 145.51 |
| 200 SMA | 164.17 |
| RSI 14 | 42.93 |
| FCF TTM | 1,626,837,000 |
| SBC / Revenue | 13.6% |
| EV / Sales | 72.65 |
| P / FCF | 214.78 |

## Business & Segment Context
Business context is intentionally grounded in validated financial scale, cash generation, balance-sheet and source-quality claims. Segment-specific interpretation should only be expanded when validated segment evidence is available.

## Fundamental Analysis
- **PLTR_CLAIM_002**: Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion.
  Counterargument: Revenue scale alone does not prove attractive returns or valuation discipline.
  Investment implication: Use revenue evidence as context, not as a standalone buy signal.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028`.
- **PLTR_CLAIM_003**: Free cash flow is a central quality check and should be interpreted only from the validated packet value.
  Counterargument: FCF may be company-defined or period-sensitive and can require reconciliation review.
  Investment implication: FCF quality supports the thesis only if no sanity guard blocks the report.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **PLTR_CLAIM_004**: Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation.
  Counterargument: High-growth software companies may tolerate higher SBC while scaling.
  Investment implication: Treat SBC as a risk modifier rather than an automatic rating override.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_SBC_TO_REVENUE, PLTR_SEC_DERIVED_SBC_TO_REVENUE`.
- **PLTR_CLAIM_005**: Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims.
  Investment implication: A stronger liquidity position can widen the acceptable holding corridor.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_CASH, PLTR_SEC_COMPANYFACTS_1321655_CASH_AND_EQUIVALENTS, PLTR_SEC_COMPANYFACTS_1321655_CASH_AND_INVESTMENTS, PLTR_SEC_COMPANYFACTS_1321655_NET_CASH, PLTR_SEC_cash_and_equivalents_FY2025_FY_0001321655-26-000011, PLTR_SEC_cash_and_equivalents_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_DEBT, PLTR_SEC_COMPANYFACTS_1321655_NET_DEBT, PLTR_SEC_COMPANYFACTS_1321655_TOTAL_DEBT`.

## Valuation / Multiples
- **PLTR_CLAIM_006**: Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples.
  Counterargument: Packet-derived valuation can still be blocked by sanity guards when source reconciliation is suspect.
  Investment implication: Do not upgrade rating solely from valuation language if audit has financial-sanity errors.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05`.
- **PLTR_CLAIM_007**: P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings.
  Investment implication: The rating should stay conservative when multiples are expensive or flagged.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028`.

## Technical Setup
- **PLTR_CLAIM_008**: The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation.
  Investment implication: Timing language should follow the validated technical trend state.
  Evidence IDs: `PLTR_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05`.
- **PLTR_CLAIM_009**: Moving-average structure and momentum should guide whether the action is immediate, staged or defensive.
  Counterargument: Technical weakness can be temporary if fundamentals and catalysts improve.
  Investment implication: Use staged entries or trims when technical and fundamental signals diverge.
  Evidence IDs: `PLTR_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05`.

## Bull Case
- **PLTR_CLAIM_010**: The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor.
  Counterargument: Strong scale does not resolve valuation or reconciliation anomalies.
  Investment implication: Bullish language must remain bounded by DecisionPacket permissions.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **PLTR_CLAIM_011**: A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative.
  Investment implication: Add or accumulate language should require confirmation when the preferred rating is not Buy.
  Evidence IDs: `PLTR_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05`.

## Bear Case
- **PLTR_CLAIM_012**: The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings.
  Investment implication: Manual review remains appropriate when financial-sanity guards fire.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_SBC_TO_REVENUE, PLTR_SEC_DERIVED_SBC_TO_REVENUE`.
- **PLTR_CLAIM_013**: Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit.
  Investment implication: Avoid blocked Sell language when the DecisionPacket allows only trim or hold actions.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Key Risks
- **PLTR_CLAIM_014**: Validation and audit issues are part of the research view and can override otherwise clean narrative sections.
  Investment implication: Blocking audit errors should keep the report in manual review.
  Evidence IDs: `PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05`.
- **PLTR_CLAIM_015**: Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible.
  Investment implication: Source-quality limitations belong in the final action plan.
  Evidence IDs: `PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Catalysts & Triggers
- **PLTR_CLAIM_016**: Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims.
  Investment implication: If earnings are unavailable, the report should state that limitation rather than inventing timing.
  Evidence IDs: `PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05`.
- **PLTR_CLAIM_017**: Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet.
  Investment implication: Use confirmation language instead of hard price targets unless risk/reward levels are validated.
  Evidence IDs: `PLTR_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05`.

- Earnings date unavailable in validated packet; no earnings event-risk claim is made.

## Scenario View
- Base case: use `Hold` as the committee anchor.
- Bull case: move only within the allowed rating corridor if validated fundamentals and technical confirmation improve.
- Bear case: downgrade only within the allowed rating corridor unless new validated blocking evidence appears.

## Final Rating & Action Plan
Final Rating: Hold

Allowed ratings: Hold, Tactical Trim, Tactical Underweight. Blocked ratings: Strong Buy, Buy, Accumulate, Underweight, Sell, Avoid.

Primary action: Maintain existing position.
New money: Wait for confirmation or better entry.

- **PLTR_CLAIM_018**: The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor.
  Counterargument: Another allowed rating may be defensible, but blocked ratings are not allowed.
  Investment implication: Final report wording must choose Hold or another allowed rating with explicit justification.
  Evidence IDs: `PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05`.

## Evidence Appendix
| Claim ID | Claim | Evidence IDs | Source Type | Confidence | Metric Refs |
|---|---|---|---|---|---|
| PLTR_CLAIM_001 | PLTR enters the report with a validated Hold rating corridor and a price basis frozen before interpretation. | PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| PLTR_CLAIM_002 | Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion. | PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028 | sec_filing | high | revenue_ttm |
| PLTR_CLAIM_003 | Free cash flow is a central quality check and should be interpreted only from the validated packet value. | PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | high | free_cash_flow_ttm |
| PLTR_CLAIM_004 | Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation. | PLTR_SEC_COMPANYFACTS_1321655_SBC_TO_REVENUE, PLTR_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | sbc_to_revenue |
| PLTR_CLAIM_005 | Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims. | PLTR_SEC_COMPANYFACTS_1321655_CASH, PLTR_SEC_COMPANYFACTS_1321655_CASH_AND_EQUIVALENTS, PLTR_SEC_COMPANYFACTS_1321655_CASH_AND_INVESTMENTS, PLTR_SEC_COMPANYFACTS_1321655_NET_CASH, PLTR_SEC_cash_and_equivalents_FY2025_FY_0001321655-26-000011, PLTR_SEC_cash_and_equivalents_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_DEBT, PLTR_SEC_COMPANYFACTS_1321655_NET_DEBT, PLTR_SEC_COMPANYFACTS_1321655_TOTAL_DEBT | sec_filing | medium | net_cash, total_debt |
| PLTR_CLAIM_006 | Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples. | PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv, sec_filing | medium | revenue_ttm, free_cash_flow_ttm, close |
| PLTR_CLAIM_007 | P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings. | PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028 | sec_filing | medium | free_cash_flow_ttm, revenue_ttm |
| PLTR_CLAIM_008 | The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation. | PLTR_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | technical_indicators, close |
| PLTR_CLAIM_009 | Moving-average structure and momentum should guide whether the action is immediate, staged or defensive. | PLTR_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| PLTR_CLAIM_010 | The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor. | PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| PLTR_CLAIM_011 | A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative. | PLTR_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| PLTR_CLAIM_012 | The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings. | PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_SBC_TO_REVENUE, PLTR_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | free_cash_flow_ttm, sbc_to_revenue |
| PLTR_CLAIM_013 | Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit. | PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| PLTR_CLAIM_014 | Validation and audit issues are part of the research view and can override otherwise clean narrative sections. | PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| PLTR_CLAIM_015 | Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible. | PLTR_SEC_COMPANYFACTS_1321655_REVENUE, PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM, PLTR_SEC_COMPANYFACTS_1321655_SALES, PLTR_SEC_COMPANYFACTS_1321655_UMSATZ, PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011, PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106, PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131, PLTR_SEC_revenue_FY2026_Q1_0001321655-26-000028, PLTR_SEC_COMPANYFACTS_1321655_CASHFLOW, PLTR_SEC_COMPANYFACTS_1321655_FCF, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM, PLTR_SEC_COMPANYFACTS_1321655_FREE_CASHFLOW, PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| PLTR_CLAIM_016 | Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims. | PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| PLTR_CLAIM_017 | Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet. | PLTR_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| PLTR_CLAIM_018 | The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor. | PLTR_YAHOO_CHART_PRICE_CSV_CLOSE, PLTR_YAHOO_CHART_PRICE_CSV_OHLCV, PLTR_YAHOO_CHART_PRICE_CSV_PRICE, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, PLTR_YAHOO_CHART_PRICE_CSV_PRICE_DATA, PLTR_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
