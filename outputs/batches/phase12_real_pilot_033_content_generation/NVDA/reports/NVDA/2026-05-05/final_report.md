# NVDA Research Report
## Executive Summary
- **NVDA_CLAIM_001**: NVDA enters the report with a validated Hold rating corridor and a price basis frozen before interpretation.
  Investment implication: The committee text should stay inside the Hold action frame.
  Evidence IDs: `NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05`.

## Data / Source Quality Note
- Report as-of date: `2026-05-05`.
- Price basis: `2026-05-05` close via `csv_price_provider`.
- Validation issues in packet: `1`.
- True unresolved source disagreements: `29`.

## Validated Metric Table
| Metric | Value |
|---|---:|
| Close | 196.50 |
| 50 SMA | 187.43 |
| 200 SMA | 184.10 |
| RSI 14 | 50.82 |
| FCF TTM | 60,496,000,000 |
| SBC / Revenue | 38.8% |
| EV / Sales | 435.86 |
| P / FCF | 79.63 |

## Business & Segment Context
Business context is intentionally grounded in validated financial scale, cash generation, balance-sheet and source-quality claims. Segment-specific interpretation should only be expanded when validated segment evidence is available.

## Fundamental Analysis
- **NVDA_CLAIM_002**: Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion.
  Counterargument: Revenue scale alone does not prove attractive returns or valuation discipline.
  Investment implication: Use revenue evidence as context, not as a standalone buy signal.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230`.
- **NVDA_CLAIM_003**: Free cash flow is a central quality check and should be interpreted only from the validated packet value.
  Counterargument: FCF may be company-defined or period-sensitive and can require reconciliation review.
  Investment implication: FCF quality supports the thesis only if no sanity guard blocks the report.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **NVDA_CLAIM_004**: Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation.
  Counterargument: High-growth software companies may tolerate higher SBC while scaling.
  Investment implication: Treat SBC as a risk modifier rather than an automatic rating override.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_SBC_TO_REVENUE, NVDA_SEC_DERIVED_SBC_TO_REVENUE`.
- **NVDA_CLAIM_005**: Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims.
  Investment implication: A stronger liquidity position can widen the acceptable holding corridor.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_CASH, NVDA_SEC_COMPANYFACTS_1045810_CASH_AND_EQUIVALENTS, NVDA_SEC_COMPANYFACTS_1045810_CASH_AND_INVESTMENTS, NVDA_SEC_COMPANYFACTS_1045810_NET_CASH, NVDA_SEC_cash_and_equivalents_FY2026_FY_0001045810-26-000021, NVDA_SEC_cash_and_equivalents_FY2026_Q2_0001045810-25-000209, NVDA_SEC_cash_and_equivalents_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_DEBT, NVDA_SEC_COMPANYFACTS_1045810_NET_DEBT, NVDA_SEC_COMPANYFACTS_1045810_TOTAL_DEBT`.

## Valuation / Multiples
- **NVDA_CLAIM_006**: Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples.
  Counterargument: Packet-derived valuation can still be blocked by sanity guards when source reconciliation is suspect.
  Investment implication: Do not upgrade rating solely from valuation language if audit has financial-sanity errors.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05`.
- **NVDA_CLAIM_007**: P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings.
  Investment implication: The rating should stay conservative when multiples are expensive or flagged.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230`.

## Technical Setup
- **NVDA_CLAIM_008**: The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation.
  Investment implication: Timing language should follow the validated technical trend state.
  Evidence IDs: `NVDA_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05`.
- **NVDA_CLAIM_009**: Moving-average structure and momentum should guide whether the action is immediate, staged or defensive.
  Counterargument: Technical weakness can be temporary if fundamentals and catalysts improve.
  Investment implication: Use staged entries or trims when technical and fundamental signals diverge.
  Evidence IDs: `NVDA_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05`.

## Bull Case
- **NVDA_CLAIM_010**: The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor.
  Counterargument: Strong scale does not resolve valuation or reconciliation anomalies.
  Investment implication: Bullish language must remain bounded by DecisionPacket permissions.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **NVDA_CLAIM_011**: A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative.
  Investment implication: Add or accumulate language should require confirmation when the preferred rating is not Buy.
  Evidence IDs: `NVDA_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05`.

## Bear Case
- **NVDA_CLAIM_012**: The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings.
  Investment implication: Manual review remains appropriate when financial-sanity guards fire.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_SBC_TO_REVENUE, NVDA_SEC_DERIVED_SBC_TO_REVENUE`.
- **NVDA_CLAIM_013**: Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit.
  Investment implication: Avoid blocked Sell language when the DecisionPacket allows only trim or hold actions.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Key Risks
- **NVDA_CLAIM_014**: Validation and audit issues are part of the research view and can override otherwise clean narrative sections.
  Investment implication: Blocking audit errors should keep the report in manual review.
  Evidence IDs: `NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05`.
- **NVDA_CLAIM_015**: Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible.
  Investment implication: Source-quality limitations belong in the final action plan.
  Evidence IDs: `NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Catalysts & Triggers
- **NVDA_CLAIM_016**: Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims.
  Investment implication: If earnings are unavailable, the report should state that limitation rather than inventing timing.
  Evidence IDs: `NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05`.
- **NVDA_CLAIM_017**: Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet.
  Investment implication: Use confirmation language instead of hard price targets unless risk/reward levels are validated.
  Evidence IDs: `NVDA_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05`.

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

- **NVDA_CLAIM_018**: The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor.
  Counterargument: Another allowed rating may be defensible, but blocked ratings are not allowed.
  Investment implication: Final report wording must choose Hold or another allowed rating with explicit justification.
  Evidence IDs: `NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05`.

## Evidence Appendix
| Claim ID | Claim | Evidence IDs | Source Type | Confidence | Metric Refs |
|---|---|---|---|---|---|
| NVDA_CLAIM_001 | NVDA enters the report with a validated Hold rating corridor and a price basis frozen before interpretation. | NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| NVDA_CLAIM_002 | Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion. | NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230 | sec_filing | high | revenue_ttm |
| NVDA_CLAIM_003 | Free cash flow is a central quality check and should be interpreted only from the validated packet value. | NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | high | free_cash_flow_ttm |
| NVDA_CLAIM_004 | Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation. | NVDA_SEC_COMPANYFACTS_1045810_SBC_TO_REVENUE, NVDA_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | sbc_to_revenue |
| NVDA_CLAIM_005 | Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims. | NVDA_SEC_COMPANYFACTS_1045810_CASH, NVDA_SEC_COMPANYFACTS_1045810_CASH_AND_EQUIVALENTS, NVDA_SEC_COMPANYFACTS_1045810_CASH_AND_INVESTMENTS, NVDA_SEC_COMPANYFACTS_1045810_NET_CASH, NVDA_SEC_cash_and_equivalents_FY2026_FY_0001045810-26-000021, NVDA_SEC_cash_and_equivalents_FY2026_Q2_0001045810-25-000209, NVDA_SEC_cash_and_equivalents_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_DEBT, NVDA_SEC_COMPANYFACTS_1045810_NET_DEBT, NVDA_SEC_COMPANYFACTS_1045810_TOTAL_DEBT | sec_filing | medium | net_cash, total_debt |
| NVDA_CLAIM_006 | Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples. | NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv, sec_filing | medium | revenue_ttm, free_cash_flow_ttm, close |
| NVDA_CLAIM_007 | P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings. | NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230 | sec_filing | medium | free_cash_flow_ttm, revenue_ttm |
| NVDA_CLAIM_008 | The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation. | NVDA_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | technical_indicators, close |
| NVDA_CLAIM_009 | Moving-average structure and momentum should guide whether the action is immediate, staged or defensive. | NVDA_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| NVDA_CLAIM_010 | The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor. | NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| NVDA_CLAIM_011 | A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative. | NVDA_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| NVDA_CLAIM_012 | The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings. | NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_SBC_TO_REVENUE, NVDA_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | free_cash_flow_ttm, sbc_to_revenue |
| NVDA_CLAIM_013 | Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit. | NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| NVDA_CLAIM_014 | Validation and audit issues are part of the research view and can override otherwise clean narrative sections. | NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| NVDA_CLAIM_015 | Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible. | NVDA_SEC_COMPANYFACTS_1045810_REVENUE, NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM, NVDA_SEC_COMPANYFACTS_1045810_SALES, NVDA_SEC_COMPANYFACTS_1045810_UMSATZ, NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021, NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209, NVDA_SEC_revenue_FY2026_Q3_0001045810-25-000230, NVDA_SEC_COMPANYFACTS_1045810_CASHFLOW, NVDA_SEC_COMPANYFACTS_1045810_FCF, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM, NVDA_SEC_COMPANYFACTS_1045810_FREE_CASHFLOW, NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| NVDA_CLAIM_016 | Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims. | NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| NVDA_CLAIM_017 | Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet. | NVDA_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| NVDA_CLAIM_018 | The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor. | NVDA_YAHOO_CHART_PRICE_CSV_CLOSE, NVDA_YAHOO_CHART_PRICE_CSV_OHLCV, NVDA_YAHOO_CHART_PRICE_CSV_PRICE, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NVDA_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NVDA_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
