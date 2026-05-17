# NOW Research Report
## Executive Summary
- **NOW_CLAIM_001**: NOW enters the report with a validated Hold rating corridor and a price basis frozen before interpretation.
  Investment implication: The committee text should stay inside the Hold action frame.
  Evidence IDs: `NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05`.

## Data / Source Quality Note
- Report as-of date: `2026-05-05`.
- Price basis: `2026-05-05` close via `csv_price_provider`.
- Validation issues in packet: `1`.
- True unresolved source disagreements: `15`.

## Validated Metric Table
| Metric | Value |
|---|---:|
| Close | 92.01 |
| 50 SMA | 102.82 |
| 200 SMA | 148.97 |
| RSI 14 | 44.88 |
| FCF TTM | 5,679,000,000 |
| SBC / Revenue | 617.2% |
| EV / Sales | 301.89 |
| P / FCF | 16.85 |

## Business & Segment Context
Business context is intentionally grounded in validated financial scale, cash generation, balance-sheet and source-quality claims. Segment-specific interpretation should only be expanded when validated segment evidence is available.

## Fundamental Analysis
- **NOW_CLAIM_002**: Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion.
  Counterargument: Revenue scale alone does not prove attractive returns or valuation discipline.
  Investment implication: Use revenue evidence as context, not as a standalone buy signal.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056`.
- **NOW_CLAIM_003**: Free cash flow is a central quality check and should be interpreted only from the validated packet value.
  Counterargument: FCF may be company-defined or period-sensitive and can require reconciliation review.
  Investment implication: FCF quality supports the thesis only if no sanity guard blocks the report.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **NOW_CLAIM_004**: Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation.
  Counterargument: High-growth software companies may tolerate higher SBC while scaling.
  Investment implication: Treat SBC as a risk modifier rather than an automatic rating override.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_SBC_TO_REVENUE, NOW_SEC_DERIVED_SBC_TO_REVENUE`.
- **NOW_CLAIM_005**: Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims.
  Investment implication: A stronger liquidity position can widen the acceptable holding corridor.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_CASH, NOW_SEC_COMPANYFACTS_1373715_CASH_AND_EQUIVALENTS, NOW_SEC_COMPANYFACTS_1373715_CASH_AND_INVESTMENTS, NOW_SEC_COMPANYFACTS_1373715_NET_CASH, NOW_SEC_cash_and_equivalents_FY2025_FY_0001373715-26-000007, NOW_SEC_cash_and_equivalents_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_DEBT, NOW_SEC_COMPANYFACTS_1373715_NET_DEBT, NOW_SEC_COMPANYFACTS_1373715_TOTAL_DEBT`.

## Valuation / Multiples
- **NOW_CLAIM_006**: Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples.
  Counterargument: Packet-derived valuation can still be blocked by sanity guards when source reconciliation is suspect.
  Investment implication: Do not upgrade rating solely from valuation language if audit has financial-sanity errors.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05`.
- **NOW_CLAIM_007**: P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings.
  Investment implication: The rating should stay conservative when multiples are expensive or flagged.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056`.

## Technical Setup
- **NOW_CLAIM_008**: The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation.
  Investment implication: Timing language should follow the validated technical trend state.
  Evidence IDs: `NOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05`.
- **NOW_CLAIM_009**: Moving-average structure and momentum should guide whether the action is immediate, staged or defensive.
  Counterargument: Technical weakness can be temporary if fundamentals and catalysts improve.
  Investment implication: Use staged entries or trims when technical and fundamental signals diverge.
  Evidence IDs: `NOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05`.

## Bull Case
- **NOW_CLAIM_010**: The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor.
  Counterargument: Strong scale does not resolve valuation or reconciliation anomalies.
  Investment implication: Bullish language must remain bounded by DecisionPacket permissions.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM`.
- **NOW_CLAIM_011**: A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative.
  Investment implication: Add or accumulate language should require confirmation when the preferred rating is not Buy.
  Evidence IDs: `NOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05`.

## Bear Case
- **NOW_CLAIM_012**: The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings.
  Investment implication: Manual review remains appropriate when financial-sanity guards fire.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_SBC_TO_REVENUE, NOW_SEC_DERIVED_SBC_TO_REVENUE`.
- **NOW_CLAIM_013**: Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit.
  Investment implication: Avoid blocked Sell language when the DecisionPacket allows only trim or hold actions.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Key Risks
- **NOW_CLAIM_014**: Validation and audit issues are part of the research view and can override otherwise clean narrative sections.
  Investment implication: Blocking audit errors should keep the report in manual review.
  Evidence IDs: `NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05`.
- **NOW_CLAIM_015**: Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible.
  Investment implication: Source-quality limitations belong in the final action plan.
  Evidence IDs: `NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM`.

## Catalysts & Triggers
- **NOW_CLAIM_016**: Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims.
  Investment implication: If earnings are unavailable, the report should state that limitation rather than inventing timing.
  Evidence IDs: `NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05`.
- **NOW_CLAIM_017**: Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet.
  Investment implication: Use confirmation language instead of hard price targets unless risk/reward levels are validated.
  Evidence IDs: `NOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05`.

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

- **NOW_CLAIM_018**: The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor.
  Counterargument: Another allowed rating may be defensible, but blocked ratings are not allowed.
  Investment implication: Final report wording must choose Hold or another allowed rating with explicit justification.
  Evidence IDs: `NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05`.

## Evidence Appendix
| Claim ID | Claim | Evidence IDs | Source Type | Confidence | Metric Refs |
|---|---|---|---|---|---|
| NOW_CLAIM_001 | NOW enters the report with a validated Hold rating corridor and a price basis frozen before interpretation. | NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| NOW_CLAIM_002 | Revenue scale is available in the validated packet and should anchor business-quality discussion before any qualitative expansion. | NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056 | sec_filing | high | revenue_ttm |
| NOW_CLAIM_003 | Free cash flow is a central quality check and should be interpreted only from the validated packet value. | NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | high | free_cash_flow_ttm |
| NOW_CLAIM_004 | Stock-based compensation needs explicit review because dilution economics can change the quality of reported cash generation. | NOW_SEC_COMPANYFACTS_1373715_SBC_TO_REVENUE, NOW_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | sbc_to_revenue |
| NOW_CLAIM_005 | Balance-sheet flexibility is assessed through validated cash and debt references rather than narrative balance-sheet claims. | NOW_SEC_COMPANYFACTS_1373715_CASH, NOW_SEC_COMPANYFACTS_1373715_CASH_AND_EQUIVALENTS, NOW_SEC_COMPANYFACTS_1373715_CASH_AND_INVESTMENTS, NOW_SEC_COMPANYFACTS_1373715_NET_CASH, NOW_SEC_cash_and_equivalents_FY2025_FY_0001373715-26-000007, NOW_SEC_cash_and_equivalents_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_DEBT, NOW_SEC_COMPANYFACTS_1373715_NET_DEBT, NOW_SEC_COMPANYFACTS_1373715_TOTAL_DEBT | sec_filing | medium | net_cash, total_debt |
| NOW_CLAIM_006 | Valuation is framed from validated revenue, FCF and price-basis evidence, not from manually recomputed multiples. | NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv, sec_filing | medium | revenue_ttm, free_cash_flow_ttm, close |
| NOW_CLAIM_007 | P/FCF and EV/Sales should be treated as risk controls when available, especially when the DecisionPacket limits aggressive ratings. | NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056 | sec_filing | medium | free_cash_flow_ttm, revenue_ttm |
| NOW_CLAIM_008 | The technical setup is based on the frozen OHLCV-derived indicator packet rather than fresh chart interpretation. | NOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | technical_indicators, close |
| NOW_CLAIM_009 | Moving-average structure and momentum should guide whether the action is immediate, staged or defensive. | NOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| NOW_CLAIM_010 | The bull case starts with validated revenue and FCF evidence: operating scale and cash conversion can support a constructive rating corridor. | NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| NOW_CLAIM_011 | A constructive bull path requires technical confirmation from the validated indicator set rather than an unsupported price narrative. | NOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| NOW_CLAIM_012 | The bear case centers on FCF quality, SBC pressure and any audit-level sanity warnings. | NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_SBC_TO_REVENUE, NOW_SEC_DERIVED_SBC_TO_REVENUE | sec_filing | medium | free_cash_flow_ttm, sbc_to_revenue |
| NOW_CLAIM_013 | Valuation risk should be interpreted as a discipline constraint, not as a standalone Sell call unless the action policy supports exit. | NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| NOW_CLAIM_014 | Validation and audit issues are part of the research view and can override otherwise clean narrative sections. | NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| NOW_CLAIM_015 | Low-confidence or disputed source reconciliation should reduce conviction even when the mechanical rating appears plausible. | NOW_SEC_COMPANYFACTS_1373715_REVENUE, NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM, NOW_SEC_COMPANYFACTS_1373715_SALES, NOW_SEC_COMPANYFACTS_1373715_UMSATZ, NOW_SEC_revenue_FY2025_FY_0001373715-26-000007, NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276, NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309, NOW_SEC_revenue_FY2026_Q1_0001373715-26-000056, NOW_SEC_COMPANYFACTS_1373715_CASHFLOW, NOW_SEC_COMPANYFACTS_1373715_FCF, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW, NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM, NOW_SEC_COMPANYFACTS_1373715_FREE_CASHFLOW, NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM | sec_filing | medium | revenue_ttm, free_cash_flow_ttm |
| NOW_CLAIM_016 | Catalysts are limited to confirmed packet inputs; unavailable earnings dates must not be converted into event-risk claims. | NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
| NOW_CLAIM_017 | Trigger language should reference validated support, resistance or trend confirmation only when produced by the technical packet. | NOW_YAHOO_CHART_PRICE_CSV_TECHNICAL_INDICATORS, NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | medium | technical_indicators, close |
| NOW_CLAIM_018 | The final action should use Hold, because the DecisionPacket identifies it as the preferred rating within the allowed corridor. | NOW_YAHOO_CHART_PRICE_CSV_CLOSE, NOW_YAHOO_CHART_PRICE_CSV_OHLCV, NOW_YAHOO_CHART_PRICE_CSV_PRICE, NOW_YAHOO_CHART_PRICE_CSV_PRICE_BASIS, NOW_YAHOO_CHART_PRICE_CSV_PRICE_DATA, NOW_CSV_PRICE_CLOSE_2026-05-05 | exchange_ohlcv | high | close |
