# AMD Research Report
## Executive Summary
- **AMD_CLAIM_001**: AMD enters the report with a validated Hold rating corridor and a price basis frozen before interpretation.
  Investment implication: The committee text should stay inside the Hold action frame.
  Evidence IDs: `AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05`.

## Data / Source Quality Note
- Report as-of date: `2026-05-05`.
- Price basis: `2026-05-05` close via `csv_price_provider`.
- Validation issues in packet: `1`.
- True unresolved source disagreements: `14`.

## Validated Metric Table
| Metric | Value |
|---|---:|
| Close | 355.26 |
| 50 SMA | 241.38 |
| 200 SMA | 213.28 |
| RSI 14 | 72.54 |
| FCF TTM | 1,813,000,000 |
| SBC / Revenue | 22.1% |
| EV / Sales | 89.99 |
| P / FCF | 320.58 |

## Business & Segment Context
Business context is intentionally grounded in validated financial scale, cash generation, balance-sheet and source-quality claims. Segment-specific interpretation should only be expanded when validated segment evidence is available.

## Fundamental Analysis
- **AMD_CLAIM_002**: Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion.
  Counterargument: Revenue scale alone does not prove attractive returns or valuation discipline.
  Investment implication: Use revenue evidence as context, not as a standalone buy signal.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166`.
- **AMD_CLAIM_003**: Free cash flow is a central quality check and should be interpreted only from the validated packet value.
  Counterargument: FCF may be company-defined or period-sensitive and can require reconciliation review.
  Investment implication: FCF quality supports the thesis only if no sanity guard blocks the report.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **AMD_CLAIM_004**: Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation.
  Counterargument: High-growth software companies may tolerate higher SBC while scaling.
  Investment implication: Treat SBC as a risk modifier rather than an automatic rating override.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_SBC_TO_REVENUE, AMD_SEC_DERIVED_SBC_TO_REVENUE`.
- **AMD_CLAIM_005**: Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims.
  Investment implication: A stronger liquidity position can widen the acceptable holding corridor.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_CASH, AMD_SEC_COMPANYFACTS_2488_CASH_AND_EQUIVALENTS, AMD_SEC_COMPANYFACTS_2488_CASH_AND_INVESTMENTS, AMD_SEC_COMPANYFACTS_2488_NET_CASH, AMD_SEC_cash_and_equivalents_FY2025_FY_0000002488-26-000018, AMD_SEC_cash_and_equivalents_FY2025_Q1_0000002488-25-000047, AMD_SEC_cash_and_equivalents_FY2025_Q2_0000002488-25-000108, AMD_SEC_cash_and_equivalents_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_DEBT, AMD_SEC_COMPANYFACTS_2488_NET_DEBT, AMD_SEC_COMPANYFACTS_2488_TOTAL_DEBT`.

## Valuation / Multiples
- **AMD_CLAIM_006**: Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples.
  Counterargument: Packet-derived valuation can still be blocked by sanity guards when source reconciliation is suspect.
  Investment implication: Do not upgrade rating solely from valuation language if audit has financial-sanity errors.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05`.
- **AMD_CLAIM_007**: P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings.
  Investment implication: The rating should stay conservative when multiples are expensive or flagged.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166`.

## Technical Setup
- **AMD_CLAIM_008**: The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation.
  Investment implication: Timing language should follow the validated technical trend state.
  Evidence IDs: `AMD_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05`.
- **AMD_CLAIM_009**: Moving-average structure and momentum should guide whether the action is immediate, staged or defensive.
  Counterargument: Technical weakness can be temporary if fundamentals and catalysts improve.
  Investment implication: Use staged entries or trims when technical and fundamental signals diverge.
  Evidence IDs: `AMD_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05`.

## Bull Case
- **AMD_CLAIM_010**: The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor.
  Counterargument: Strong scale does not resolve valuation or reconciliation anomalies.
  Investment implication: Bullish language must remain bounded by DecisionPacket permissions.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **AMD_CLAIM_011**: A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative.
  Investment implication: Add or accumulate language should require confirmation when the preferred rating is not Buy.
  Evidence IDs: `AMD_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05`.

## Bear Case
- **AMD_CLAIM_012**: The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings.
  Investment implication: Manual review remains appropriate when financial-sanity guards fire.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_SBC_TO_REVENUE, AMD_SEC_DERIVED_SBC_TO_REVENUE`.
- **AMD_CLAIM_013**: Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit.
  Investment implication: Avoid blocked Sell language when the DecisionPacket allows only trim or hold actions.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Key Risks
- **AMD_CLAIM_014**: Validation and audit issues are part of the research view and can override otherwise clean narrative sections.
  Investment implication: Blocking audit errors should keep the report in manual review.
  Evidence IDs: `AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05`.
- **AMD_CLAIM_015**: Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible.
  Investment implication: Source-quality limitations belong in the final action plan.
  Evidence IDs: `AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Catalysts & Triggers
- **AMD_CLAIM_016**: Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims.
  Investment implication: If earnings are unavailable, the report should state that limitation rather than inventing timing.
  Evidence IDs: `AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05`.
- **AMD_CLAIM_017**: Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet.
  Investment implication: Use confirmation language instead of hard price targets unless risk/reward levels are validated.
  Evidence IDs: `AMD_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05`.

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

- **AMD_CLAIM_018**: The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor.
  Counterargument: Another allowed rating may be defensible, but blocked ratings are not allowed.
  Investment implication: Final report wording must choose Hold or another allowed rating with explicit justification.
  Evidence IDs: `AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05`.

## Evidence Appendix
| Claim ID | Claim | Evidence IDs | Source Type | Confidence | Metric Refs |
|---|---|---|---|---|---|
| AMD_CLAIM_001 | AMD enters the report with a validated Hold rating corridor and a price basis frozen before interpretation. | AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| AMD_CLAIM_002 | Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion. | AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166 | sec_filing | high | revenue_ttm |
| AMD_CLAIM_003 | Free cash flow is a central quality check and should be interpreted only from the validated packet value. | AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | high | free_cash_flow_ttm |
| AMD_CLAIM_004 | Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation. | AMD_SEC_COMPANYFACTS_2488_SBC_TO_REVENUE, AMD_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | sbc_to_revenue |
| AMD_CLAIM_005 | Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims. | AMD_SEC_COMPANYFACTS_2488_CASH, AMD_SEC_COMPANYFACTS_2488_CASH_AND_EQUIVALENTS, AMD_SEC_COMPANYFACTS_2488_CASH_AND_INVESTMENTS, AMD_SEC_COMPANYFACTS_2488_NET_CASH, AMD_SEC_cash_and_equivalents_FY2025_FY_0000002488-26-000018, AMD_SEC_cash_and_equivalents_FY2025_Q1_0000002488-25-000047, AMD_SEC_cash_and_equivalents_FY2025_Q2_0000002488-25-000108, AMD_SEC_cash_and_equivalents_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_DEBT, AMD_SEC_COMPANYFACTS_2488_NET_DEBT, AMD_SEC_COMPANYFACTS_2488_TOTAL_DEBT | sec_filing | medium | net_cash, total_debt |
| AMD_CLAIM_006 | Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples. | AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv, sec_filing | medium | revenue_ttm, free_cash_flow_ttm, close |
| AMD_CLAIM_007 | P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings. | AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166 | sec_filing | medium | free_cash_flow_ttm, revenue_ttm |
| AMD_CLAIM_008 | The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation. | AMD_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | technical_indicators, close |
| AMD_CLAIM_009 | Moving-average structure and momentum should guide whether the action is immediate, staged or defensive. | AMD_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| AMD_CLAIM_010 | The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor. | AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| AMD_CLAIM_011 | A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative. | AMD_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| AMD_CLAIM_012 | The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings. | AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_SBC_TO_REVENUE, AMD_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | free_cash_flow_ttm, sbc_to_revenue |
| AMD_CLAIM_013 | Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit. | AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| AMD_CLAIM_014 | Validation and audit issues are part of the research view and can override otherwise clean narrative sections. | AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| AMD_CLAIM_015 | Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible. | AMD_SEC_COMPANYFACTS_2488_REVENUE, AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM, AMD_SEC_COMPANYFACTS_2488_SALES, AMD_SEC_COMPANYFACTS_2488_UMSATZ, AMD_SEC_revenue_FY2025_FY_0000002488-26-000018, AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108, AMD_SEC_revenue_FY2025_Q3_0000002488-25-000166, AMD_SEC_COMPANYFACTS_2488_CASHFLOW, AMD_SEC_COMPANYFACTS_2488_FCF, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW, AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM, AMD_SEC_COMPANYFACTS_2488_FREE_CASHFLOW, AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| AMD_CLAIM_016 | Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims. | AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| AMD_CLAIM_017 | Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet. | AMD_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| AMD_CLAIM_018 | The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor. | AMD_YAHOO_CHART_PRICE_CSV_CLOSE, AMD_YAHOO_CHART_PRICE_CSV_OHLCV, AMD_YAHOO_CHART_PRICE_CSV_PRICE, AMD_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, AMD_YAHOO_CHART_PRICE_CSV_PRICE_DATA, AMD_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
