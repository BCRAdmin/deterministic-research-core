# ORCL Research Report
## Executive Summary
- **ORCL_CLAIM_001**: ORCL enters the report with a validated Hold rating corridor and a price basis frozen before interpretation.
  Investment implication: The committee text should stay inside the Hold action frame.
  Evidence IDs: `ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05`.

## Data / Source Quality Note
- Report as-of date: `2026-05-05`.
- Price basis: `2026-05-05` close via `csv_price_provider`.
- Validation issues in packet: `1`.
- True unresolved source disagreements: `3`.

## Validated Metric Table
| Metric | Value |
|---|---:|
| Close | 185.35 |
| 50 SMA | 157.00 |
| 200 SMA | 211.68 |
| RSI 14 | 64.39 |
| FCF TTM | 15,546,000,000 |
| SBC / Revenue | 7.7% |
| EV / Sales | 8.05 |
| P / FCF | 34.72 |

## Business & Segment Context
Business context is intentionally grounded in validated financial scale, cash generation, balance-sheet and source-quality claims. Segment-specific interpretation should only be expanded when validated segment evidence is available.

## Fundamental Analysis
- **ORCL_CLAIM_002**: Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion.
  Counterargument: Revenue scale alone does not prove attractive returns or valuation discipline.
  Investment implication: Use revenue evidence as context, not as a standalone buy signal.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045`.
- **ORCL_CLAIM_003**: Free cash flow is a central quality check and should be interpreted only from the validated packet value.
  Counterargument: FCF may be company-defined or period-sensitive and can require reconciliation review.
  Investment implication: FCF quality supports the thesis only if no sanity guard blocks the report.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **ORCL_CLAIM_004**: Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation.
  Counterargument: High-growth software companies may tolerate higher SBC while scaling.
  Investment implication: Treat SBC as a risk modifier rather than an automatic rating override.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_SBC_TO_REVENUE, ORCL_SEC_DERIVED_SBC_TO_REVENUE`.
- **ORCL_CLAIM_005**: Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims.
  Investment implication: A stronger liquidity position can widen the acceptable holding corridor.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_CASH, ORCL_SEC_COMPANYFACTS_1341439_CASH_AND_EQUIVALENTS, ORCL_SEC_COMPANYFACTS_1341439_CASH_AND_INVESTMENTS, ORCL_SEC_COMPANYFACTS_1341439_NET_CASH, ORCL_SEC_cash_and_equivalents_FY2025_FY_0000950170-25-087926, ORCL_SEC_cash_and_equivalents_FY2026_Q3_0001193125-26-101045, ORCL_SEC_cash_and_equivalents_FY2026_Q1_0001193125-25-200095, ORCL_SEC_cash_and_equivalents_FY2026_Q2_0001193125-25-315925, ORCL_SEC_COMPANYFACTS_1341439_DEBT, ORCL_SEC_COMPANYFACTS_1341439_NET_DEBT, ORCL_SEC_COMPANYFACTS_1341439_TOTAL_DEBT`.

## Valuation / Multiples
- **ORCL_CLAIM_006**: Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples.
  Counterargument: Packet-derived valuation can still be blocked by sanity guards when source reconciliation is suspect.
  Investment implication: Do not upgrade rating solely from valuation language if audit has financial-sanity errors.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045, ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05`.
- **ORCL_CLAIM_007**: P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings.
  Investment implication: The rating should stay conservative when multiples are expensive or flagged.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045`.

## Technical Setup
- **ORCL_CLAIM_008**: The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation.
  Investment implication: Timing language should follow the validated technical trend state.
  Evidence IDs: `ORCL_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05`.
- **ORCL_CLAIM_009**: Moving-average structure and momentum should guide whether the action is immediate, staged or defensive.
  Counterargument: Technical weakness can be temporary if fundamentals and catalysts improve.
  Investment implication: Use staged entries or trims when technical and fundamental signals diverge.
  Evidence IDs: `ORCL_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05`.

## Bull Case
- **ORCL_CLAIM_010**: The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor.
  Counterargument: Strong scale does not resolve valuation or reconciliation anomalies.
  Investment implication: Bullish language must remain bounded by DecisionPacket permissions.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045, ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **ORCL_CLAIM_011**: A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative.
  Investment implication: Add or accumulate language should require confirmation when the preferred rating is not Buy.
  Evidence IDs: `ORCL_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05`.

## Bear Case
- **ORCL_CLAIM_012**: The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings.
  Investment implication: Manual review remains appropriate when financial-sanity guards fire.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_SBC_TO_REVENUE, ORCL_SEC_DERIVED_SBC_TO_REVENUE`.
- **ORCL_CLAIM_013**: Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit.
  Investment implication: Avoid blocked Sell language when the DecisionPacket allows only trim or hold actions.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045, ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Key Risks
- **ORCL_CLAIM_014**: Validation and audit issues are part of the research view and can override otherwise clean narrative sections.
  Investment implication: Blocking audit errors should keep the report in manual review.
  Evidence IDs: `ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05`.
- **ORCL_CLAIM_015**: Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible.
  Investment implication: Source-quality limitations belong in the final action plan.
  Evidence IDs: `ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045, ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Catalysts & Triggers
- **ORCL_CLAIM_016**: Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims.
  Investment implication: If earnings are unavailable, the report should state that limitation rather than inventing timing.
  Evidence IDs: `ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05`.
- **ORCL_CLAIM_017**: Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet.
  Investment implication: Use confirmation language instead of hard price targets unless risk/reward levels are validated.
  Evidence IDs: `ORCL_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05`.

- Earnings date unavailable in validated packet; no earnings event-risk claim is made.

## Scenario View
- Base case: use `Hold` as the committee anchor.
- Bull case: move only within the allowed rating corridor if validated fundamentals and technical confirmation improve.
- Bear case: downgrade only within the allowed rating corridor unless new validated blocking evidence appears.

## Final Rating & Action Plan
Final Rating: Hold

Allowed ratings: Hold, Accumulate, Tactical Trim. Blocked ratings: Strong Buy, Buy, Tactical Underweight, Underweight, Sell, Avoid.

Primary action: Maintain existing position.
New money: Wait for confirmation or better entry.

- **ORCL_CLAIM_018**: The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor.
  Counterargument: Another allowed rating may be defensible, but blocked ratings are not allowed.
  Investment implication: Final report wording must choose Hold or another allowed rating with explicit justification.
  Evidence IDs: `ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05`.

## Evidence Appendix
| Claim ID | Claim | Evidence IDs | Source Type | Confidence | Metric Refs |
|---|---|---|---|---|---|
| ORCL_CLAIM_001 | ORCL enters the report with a validated Hold rating corridor and a price basis frozen before interpretation. | ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| ORCL_CLAIM_002 | Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion. | ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045 | sec_filing | high | revenue_ttm |
| ORCL_CLAIM_003 | Free cash flow is a central quality check and should be interpreted only from the validated packet value. | ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | high | free_cash_flow_ttm |
| ORCL_CLAIM_004 | Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation. | ORCL_SEC_COMPANYFACTS_1341439_SBC_TO_REVENUE, ORCL_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | sbc_to_revenue |
| ORCL_CLAIM_005 | Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims. | ORCL_SEC_COMPANYFACTS_1341439_CASH, ORCL_SEC_COMPANYFACTS_1341439_CASH_AND_EQUIVALENTS, ORCL_SEC_COMPANYFACTS_1341439_CASH_AND_INVESTMENTS, ORCL_SEC_COMPANYFACTS_1341439_NET_CASH, ORCL_SEC_cash_and_equivalents_FY2025_FY_0000950170-25-087926, ORCL_SEC_cash_and_equivalents_FY2026_Q3_0001193125-26-101045, ORCL_SEC_cash_and_equivalents_FY2026_Q1_0001193125-25-200095, ORCL_SEC_cash_and_equivalents_FY2026_Q2_0001193125-25-315925, ORCL_SEC_COMPANYFACTS_1341439_DEBT, ORCL_SEC_COMPANYFACTS_1341439_NET_DEBT, ORCL_SEC_COMPANYFACTS_1341439_TOTAL_DEBT | sec_filing | medium | net_cash, total_debt |
| ORCL_CLAIM_006 | Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples. | ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045, ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv, sec_filing | medium | revenue_ttm, free_cash_flow_ttm, close |
| ORCL_CLAIM_007 | P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings. | ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045 | sec_filing | medium | free_cash_flow_ttm, revenue_ttm |
| ORCL_CLAIM_008 | The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation. | ORCL_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | technical_indicators, close |
| ORCL_CLAIM_009 | Moving-average structure and momentum should guide whether the action is immediate, staged or defensive. | ORCL_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| ORCL_CLAIM_010 | The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor. | ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045, ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| ORCL_CLAIM_011 | A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative. | ORCL_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| ORCL_CLAIM_012 | The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings. | ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_SBC_TO_REVENUE, ORCL_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | free_cash_flow_ttm, sbc_to_revenue |
| ORCL_CLAIM_013 | Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit. | ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045, ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| ORCL_CLAIM_014 | Validation and audit issues are part of the research view and can override otherwise clean narrative sections. | ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| ORCL_CLAIM_015 | Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible. | ORCL_SEC_COMPANYFACTS_1341439_REVENUE, ORCL_SEC_COMPANYFACTS_1341439_REVENUE_TTM, ORCL_SEC_COMPANYFACTS_1341439_SALES, ORCL_SEC_COMPANYFACTS_1341439_UMSATZ, ORCL_SEC_revenue_FY2025_FY_0000950170-25-087926, ORCL_SEC_revenue_FY2026_Q2_0001193125-25-315925, ORCL_SEC_revenue_FY2026_Q3_0001193125-26-101045, ORCL_SEC_COMPANYFACTS_1341439_CASHFLOW, ORCL_SEC_COMPANYFACTS_1341439_FCF, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASH_FLOW_TTM, ORCL_SEC_COMPANYFACTS_1341439_FREE_CASHFLOW, ORCL_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| ORCL_CLAIM_016 | Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims. | ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| ORCL_CLAIM_017 | Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet. | ORCL_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| ORCL_CLAIM_018 | The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor. | ORCL_YAHOO_CHART_PRICE_CSV_CLOSE, ORCL_YAHOO_CHART_PRICE_CSV_OHLCV, ORCL_YAHOO_CHART_PRICE_CSV_PRICE, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, ORCL_YAHOO_CHART_PRICE_CSV_PRICE_DATA, ORCL_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
