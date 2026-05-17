# Financial Sanity Triage - Pilot 033

- Source batch: `outputs/batches/phase12_real_pilot_033_content_generation`
- Manual-review tickers triaged: `17`
- Verdict counts: `{'period_bug': 8, 'true_anomaly': 3, 'guard_too_strict': 6}`

## Summary Table

| Ticker | Verdict | Reason Codes | EV/Sales | P/FCF | FCF Margin | SBC/Revenue | Fix Direction |
|---|---|---|---:|---:|---:|---:|---|
| AMZN | `period_bug` | FINANCIAL_SANITY_FCF_MARGIN_ANOMALY | 13.80x | 28.47x | 50.2% | 9.2% | FCF margin is implausibly high for this profile; prioritize company-defined FCF where available and reconcile revenue/FCF periods before publish. |
| MSFT | `period_bug` | FINANCIAL_SANITY_FCF_MARGIN_ANOMALY | 28.89x | 45.28x | 65.3% | 11.8% | FCF margin is implausibly high for this profile; prioritize company-defined FCF where available and reconcile revenue/FCF periods before publish. |
| AAPL | `period_bug` | FINANCIAL_SANITY_FCF_MARGIN_ANOMALY | 16.19x | 29.26x | 56.0% | 5.2% | FCF margin is implausibly high for this profile; prioritize company-defined FCF where available and reconcile revenue/FCF periods before publish. |
| NVDA | `period_bug` | FINANCIAL_SANITY_EV_SALES_ABSURD, FINANCIAL_SANITY_FCF_MARGIN_ANOMALY, FINANCIAL_SANITY_SBC_REVENUE_ANOMALY | 435.86x | 79.63x | 554.1% | 38.8% | Revenue denominator is likely not a true TTM/annual comparable period; rerun PeriodResolver for annual vs quarterly/YTD facts and only derive TTM from four comparable duration facts. |
| AMD | `true_anomaly` | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY | 89.99x | 320.58x | 28.3% | 22.1% | P/FCF is extremely high even without other period red flags; keep as valuation-risk manual review unless FCF source/period is proven wrong. |
| MU | `guard_too_strict` | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY | 25.76x | 270.48x | 9.6% | 3.3% | P/FCF is above hard threshold but could be a growth/semiconductor/software context issue; consider sector-aware warning band after validating FCF period. |
| MRVL | `guard_too_strict` | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY | 19.47x | 186.08x | 10.5% | 7.5% | P/FCF is above hard threshold but could be a growth/semiconductor/software context issue; consider sector-aware warning band after validating FCF period. |
| ANET | `period_bug` | FINANCIAL_SANITY_EV_SALES_ABSURD, FINANCIAL_SANITY_FCF_MARGIN_ANOMALY, FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY | 117.85x | 109.07x | 109.7% | 17.1% | Revenue denominator is likely not a true TTM/annual comparable period; rerun PeriodResolver for annual vs quarterly/YTD facts and only derive TTM from four comparable duration facts. |
| MDB | `period_bug` | FINANCIAL_SANITY_EV_SALES_ABSURD | 116.03x | 75.34x | 157.3% | 261.4% | Revenue denominator is likely not a true TTM/annual comparable period; rerun PeriodResolver for annual vs quarterly/YTD facts and only derive TTM from four comparable duration facts. |
| CRWD | `guard_too_strict` | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY | n/a | 107.66x | n/a | n/a | P/FCF is above hard threshold but could be a growth/semiconductor/software context issue; consider sector-aware warning band after validating FCF period. |
| NET | `true_anomaly` | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY | 42.84x | 526.31x | 8.2% | 14.7% | P/FCF is extremely high even without other period red flags; keep as valuation-risk manual review unless FCF source/period is proven wrong. |
| PANW | `guard_too_strict` | FINANCIAL_SANITY_SBC_REVENUE_ANOMALY | 55.20x | n/a | n/a | 52.7% | SBC/Revenue guard fired near software profile boundaries; verify revenue period first, then either add sector context or keep manual review if ratio remains above 30%. |
| NOW | `period_bug` | FINANCIAL_SANITY_EV_SALES_ABSURD, FINANCIAL_SANITY_FCF_MARGIN_ANOMALY, FINANCIAL_SANITY_SBC_REVENUE_ANOMALY | 301.89x | 16.85x | 1836.2% | 617.2% | Revenue denominator is likely not a true TTM/annual comparable period; rerun PeriodResolver for annual vs quarterly/YTD facts and only derive TTM from four comparable duration facts. |
| INTU | `guard_too_strict` | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, FINANCIAL_SANITY_SBC_REVENUE_ANOMALY | 17.95x | 103.65x | 18.5% | 34.9% | SBC/Revenue guard fired near software profile boundaries; verify revenue period first, then either add sector context or keep manual review if ratio remains above 30%. |
| UBER | `period_bug` | FINANCIAL_SANITY_FCF_MARGIN_ANOMALY | 12.69x | 28.03x | 47.5% | 16.1% | FCF margin is implausibly high for this profile; prioritize company-defined FCF where available and reconcile revenue/FCF periods before publish. |
| TSLA | `true_anomaly` | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY | 14.73x | 5812.62x | 0.3% | 2.9% | P/FCF is extremely high even without other period red flags; keep as valuation-risk manual review unless FCF source/period is proven wrong. |
| PLTR | `guard_too_strict` | FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY | 72.65x | 214.78x | 34.6% | 13.6% | P/FCF is above hard threshold but could be a growth/semiconductor/software context issue; consider sector-aware warning band after validating FCF period. |

## Ticker Detail

### AMZN

- Verdict: `period_bug`
- Manual-review reason codes: `FINANCIAL_SANITY_FCF_MARGIN_ANOMALY`
- Market cap: `2974.583B`
- Enterprise value: `2871.857B`
- Revenue TTM: `208.125B`
- FCF TTM: `104.495B`
- SBC TTM: `19.102B`
- Shares used: `10.874B`
- Price used: `273.55`
- EV/Sales: `13.80x`
- P/FCF: `28.47x`
- FCF margin: `50.2%`
- SBC/Revenue: `9.2%`
- Fix recommendation: FCF margin is implausibly high for this profile; prioritize company-defined FCF where available and reconcile revenue/FCF periods before publish.

Evidence IDs / Source IDs:
- `revenue`: AMZN_SEC_COMPANYFACTS_1018724_REVENUE_TTM / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=208.125B / period=None; AMZN_SEC_revenue_FY2025_FY_0001018724-26-000004 / SEC_0001018724_0001018724-26-000004 / sec_filing / value=716.924B / period=FY2025_FY; AMZN_SEC_revenue_FY2025_Q2_0001018724-25-000086 / SEC_0001018724_0001018724-25-000086 / sec_filing / value=167.702B / period=FY2025_Q2; AMZN_SEC_revenue_FY2025_Q3_0001018724-25-000123 / SEC_0001018724_0001018724-25-000123 / sec_filing / value=503.538B / period=FY2025_Q3
- `fcf`: AMZN_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001018724_DERIVED_FCF / sec_filing / value=279.293B / period=TTM; AMZN_SEC_COMPANYFACTS_1018724_FREE_CASH_FLOW_TTM / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=104.495B / period=None; AMZN_SEC_COMPANYFACTS_1018724_FCF / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=n/a / period=None; AMZN_SEC_COMPANYFACTS_1018724_FREE_CASH_FLOW / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=n/a / period=None
- `sbc`: AMZN_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001018724_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.04 / period=TTM; AMZN_SEC_COMPANYFACTS_1018724_SBC_TO_REVENUE / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=0.09 / period=None; AMZN_SEC_COMPANYFACTS_1018724_SBC_TTM / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=19.102B / period=None; AMZN_SEC_sbc_FY2025_FY_0001018724-26-000004 / SEC_0001018724_0001018724-26-000004 / sec_filing / value=19.467B / period=FY2025_FY
- `shares`: AMZN_SEC_shares_diluted_FY2025_FY_0001018724-26-000004 / SEC_0001018724_0001018724-26-000004 / sec_filing / value=10.827B / period=FY2025_FY; AMZN_SEC_shares_diluted_FY2025_Q2_0001018724-25-000086 / SEC_0001018724_0001018724-25-000086 / sec_filing / value=10.806B / period=FY2025_Q2; AMZN_SEC_shares_diluted_FY2025_Q3_0001018724-25-000123 / SEC_0001018724_0001018724-25-000123 / sec_filing / value=10.815B / period=FY2025_Q3; AMZN_SEC_shares_diluted_FY2025_Q3_0001018724-25-000123 / SEC_0001018724_0001018724-25-000123 / sec_filing / value=10.845B / period=FY2025_Q3
- `debt`: AMZN_SEC_COMPANYFACTS_1018724_DEBT / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=n/a / period=None; AMZN_SEC_COMPANYFACTS_1018724_TOTAL_DEBT / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=n/a / period=None
- `cash`: AMZN_SEC_COMPANYFACTS_1018724_CASH_AND_EQUIVALENTS / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=61.453B / period=None; AMZN_SEC_COMPANYFACTS_1018724_CASH_AND_INVESTMENTS / AMZN_SEC_COMPANYFACTS_1018724 / sec_filing / value=102.726B / period=None; AMZN_SEC_cash_and_equivalents_FY2025_FY_0001018724-26-000004 / SEC_0001018724_0001018724-26-000004 / sec_filing / value=90.106B / period=FY2025_FY; AMZN_SEC_cash_and_equivalents_FY2026_Q1_0001018724-26-000014 / SEC_0001018724_0001018724-26-000014 / sec_filing / value=86.810B / period=FY2026_Q1

### MSFT

- Verdict: `period_bug`
- Manual-review reason codes: `FINANCIAL_SANITY_FCF_MARGIN_ANOMALY`
- Market cap: `3062.724B`
- Enterprise value: `2992.261B`
- Revenue TTM: `103.592B`
- FCF TTM: `67.647B`
- SBC TTM: `12.263B`
- Shares used: `7.445B`
- Price used: `411.38`
- EV/Sales: `28.89x`
- P/FCF: `45.28x`
- FCF margin: `65.3%`
- SBC/Revenue: `11.8%`
- Fix recommendation: FCF margin is implausibly high for this profile; prioritize company-defined FCF where available and reconcile revenue/FCF periods before publish.

Evidence IDs / Source IDs:
- `revenue`: MSFT_SEC_COMPANYFACTS_789019_REVENUE_TTM / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=103.592B / period=None; MSFT_SEC_revenue_FY2025_FY_0000950170-25-100235 / SEC_0000789019_0000950170-25-100235 / sec_filing / value=281.724B / period=FY2025_FY; MSFT_SEC_revenue_FY2026_Q2_0001193125-26-027207 / SEC_0000789019_0001193125-26-027207 / sec_filing / value=158.946B / period=FY2026_Q2; MSFT_SEC_revenue_FY2026_Q2_0001193125-26-027207 / SEC_0000789019_0001193125-26-027207 / sec_filing / value=81.273B / period=FY2026_Q2
- `fcf`: MSFT_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0000789019_DERIVED_FCF / sec_filing / value=100.578B / period=TTM; MSFT_SEC_COMPANYFACTS_789019_FREE_CASH_FLOW_TTM / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=67.647B / period=None; MSFT_SEC_COMPANYFACTS_789019_FCF / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=n/a / period=None; MSFT_SEC_COMPANYFACTS_789019_FREE_CASH_FLOW / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=n/a / period=None
- `sbc`: MSFT_SEC_DERIVED_SBC_TO_REVENUE / SEC_0000789019_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.04 / period=TTM; MSFT_SEC_COMPANYFACTS_789019_SBC_TO_REVENUE / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=0.12 / period=None; MSFT_SEC_COMPANYFACTS_789019_SBC_TTM / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=12.263B / period=None; MSFT_SEC_sbc_FY2025_FY_0000950170-25-100235 / SEC_0000789019_0000950170-25-100235 / sec_filing / value=11.974B / period=FY2025_FY
- `shares`: MSFT_SEC_shares_diluted_FY2025_FY_0000950170-25-100235 / SEC_0000789019_0000950170-25-100235 / sec_filing / value=7.465B / period=FY2025_FY; MSFT_SEC_shares_diluted_FY2026_Q2_0001193125-26-027207 / SEC_0000789019_0001193125-26-027207 / sec_filing / value=7.463B / period=FY2026_Q2; MSFT_SEC_shares_diluted_FY2026_Q2_0001193125-26-027207 / SEC_0000789019_0001193125-26-027207 / sec_filing / value=7.460B / period=FY2026_Q2; MSFT_SEC_shares_diluted_FY2026_Q3_0001193125-26-191507 / SEC_0000789019_0001193125-26-191507 / sec_filing / value=7.457B / period=FY2026_Q3
- `debt`: MSFT_SEC_COMPANYFACTS_789019_DEBT / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=n/a / period=None; MSFT_SEC_COMPANYFACTS_789019_TOTAL_DEBT / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=n/a / period=None
- `cash`: MSFT_SEC_COMPANYFACTS_789019_CASH_AND_EQUIVALENTS / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=24.296B / period=None; MSFT_SEC_COMPANYFACTS_789019_CASH_AND_INVESTMENTS / MSFT_SEC_COMPANYFACTS_789019 / sec_filing / value=70.463B / period=None; MSFT_SEC_cash_and_equivalents_FY2025_FY_0000950170-25-100235 / SEC_0000789019_0000950170-25-100235 / sec_filing / value=30.242B / period=FY2025_FY; MSFT_SEC_cash_and_equivalents_FY2026_Q2_0001193125-26-027207 / SEC_0000789019_0001193125-26-027207 / sec_filing / value=24.296B / period=FY2026_Q2

### AAPL

- Verdict: `period_bug`
- Manual-review reason codes: `FINANCIAL_SANITY_FCF_MARGIN_ANOMALY`
- Market cap: `4184.798B`
- Enterprise value: `4133.701B`
- Revenue TTM: `255.274B`
- FCF TTM: `143.045B`
- SBC TTM: `13.163B`
- Shares used: `14.726B`
- Price used: `284.18`
- EV/Sales: `16.19x`
- P/FCF: `29.26x`
- FCF margin: `56.0%`
- SBC/Revenue: `5.2%`
- Fix recommendation: FCF margin is implausibly high for this profile; prioritize company-defined FCF where available and reconcile revenue/FCF periods before publish.

Evidence IDs / Source IDs:
- `revenue`: AAPL_SEC_COMPANYFACTS_320193_REVENUE_TTM / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=255.274B / period=None; AAPL_SEC_revenue_FY2025_FY_0000320193-25-000079 / SEC_0000320193_0000320193-25-000079 / sec_filing / value=416.161B / period=FY2025_FY; AAPL_SEC_revenue_FY2025_Q3_0000320193-25-000073 / SEC_0000320193_0000320193-25-000073 / sec_filing / value=94.036B / period=FY2025_Q3; AAPL_SEC_revenue_FY2026_Q1_0000320193-26-000006 / SEC_0000320193_0000320193-26-000006 / sec_filing / value=143.756B / period=FY2026_Q1
- `fcf`: AAPL_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0000320193_DERIVED_FCF / sec_filing / value=249.992B / period=TTM; AAPL_SEC_COMPANYFACTS_320193_FREE_CASH_FLOW_TTM / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=143.045B / period=None; AAPL_SEC_COMPANYFACTS_320193_FCF / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=n/a / period=None; AAPL_SEC_COMPANYFACTS_320193_FREE_CASH_FLOW / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=n/a / period=None
- `sbc`: AAPL_SEC_DERIVED_SBC_TO_REVENUE / SEC_0000320193_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.04 / period=TTM; AAPL_SEC_COMPANYFACTS_320193_SBC_TO_REVENUE / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=0.05 / period=None; AAPL_SEC_COMPANYFACTS_320193_SBC_TTM / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=13.163B / period=None; AAPL_SEC_sbc_FY2025_FY_0000320193-25-000079 / SEC_0000320193_0000320193-25-000079 / sec_filing / value=12.863B / period=FY2025_FY
- `shares`: AAPL_SEC_shares_diluted_FY2025_FY_0000320193-25-000079 / SEC_0000320193_0000320193-25-000079 / sec_filing / value=15.005B / period=FY2025_FY; AAPL_SEC_shares_diluted_FY2025_Q3_0000320193-25-000073 / SEC_0000320193_0000320193-25-000073 / sec_filing / value=14.948B / period=FY2025_Q3; AAPL_SEC_shares_diluted_FY2026_Q1_0000320193-26-000006 / SEC_0000320193_0000320193-26-000006 / sec_filing / value=14.810B / period=FY2026_Q1; AAPL_SEC_shares_diluted_FY2026_Q2_0000320193-26-000013 / SEC_0000320193_0000320193-26-000013 / sec_filing / value=14.768B / period=FY2026_Q2
- `debt`: AAPL_SEC_COMPANYFACTS_320193_DEBT / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=n/a / period=None; AAPL_SEC_COMPANYFACTS_320193_TOTAL_DEBT / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=n/a / period=None
- `cash`: AAPL_SEC_COMPANYFACTS_320193_CASH_AND_EQUIVALENTS / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=28.162B / period=None; AAPL_SEC_COMPANYFACTS_320193_CASH_AND_INVESTMENTS / AAPL_SEC_COMPANYFACTS_320193 / sec_filing / value=51.097B / period=None; AAPL_SEC_cash_and_equivalents_FY2025_FY_0000320193-25-000079 / SEC_0000320193_0000320193-25-000079 / sec_filing / value=35.934B / period=FY2025_FY; AAPL_SEC_cash_and_equivalents_FY2026_Q1_0000320193-26-000006 / SEC_0000320193_0000320193-26-000006 / sec_filing / value=45.317B / period=FY2026_Q1

### NVDA

- Verdict: `period_bug`
- Manual-review reason codes: `FINANCIAL_SANITY_EV_SALES_ABSURD, FINANCIAL_SANITY_FCF_MARGIN_ANOMALY, FINANCIAL_SANITY_SBC_REVENUE_ANOMALY`
- Market cap: `4817.001B`
- Enterprise value: `4758.772B`
- Revenue TTM: `10.918B`
- FCF TTM: `60.496B`
- SBC TTM: `4.231B`
- Shares used: `24.514B`
- Price used: `196.50`
- EV/Sales: `435.86x`
- P/FCF: `79.63x`
- FCF margin: `554.1%`
- SBC/Revenue: `38.8%`
- Fix recommendation: Revenue denominator is likely not a true TTM/annual comparable period; rerun PeriodResolver for annual vs quarterly/YTD facts and only derive TTM from four comparable duration facts.

Evidence IDs / Source IDs:
- `revenue`: NVDA_SEC_COMPANYFACTS_1045810_REVENUE_TTM / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=10.918B / period=None; NVDA_SEC_revenue_FY2026_FY_0001045810-26-000021 / SEC_0001045810_0001045810-26-000021 / sec_filing / value=215.938B / period=FY2026_FY; NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209 / SEC_0001045810_0001045810-25-000209 / sec_filing / value=90.805B / period=FY2026_Q2; NVDA_SEC_revenue_FY2026_Q2_0001045810-25-000209 / SEC_0001045810_0001045810-25-000209 / sec_filing / value=46.743B / period=FY2026_Q2
- `fcf`: NVDA_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001045810_DERIVED_FCF / sec_filing / value=183.071B / period=TTM; NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW_TTM / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=60.496B / period=None; NVDA_SEC_COMPANYFACTS_1045810_FCF / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=n/a / period=None; NVDA_SEC_COMPANYFACTS_1045810_FREE_CASH_FLOW / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=n/a / period=None
- `sbc`: NVDA_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001045810_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.04 / period=TTM; NVDA_SEC_COMPANYFACTS_1045810_SBC_TO_REVENUE / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=0.39 / period=None; NVDA_SEC_COMPANYFACTS_1045810_SBC_TTM / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=4.231B / period=None; NVDA_SEC_sbc_FY2026_FY_0001045810-26-000021 / SEC_0001045810_0001045810-26-000021 / sec_filing / value=6.386B / period=FY2026_FY
- `shares`: NVDA_SEC_shares_diluted_FY2026_FY_0001045810-26-000021 / SEC_0001045810_0001045810-26-000021 / sec_filing / value=24.514B / period=FY2026_FY; NVDA_SEC_shares_diluted_FY2026_Q2_0001045810-25-000209 / SEC_0001045810_0001045810-25-000209 / sec_filing / value=24.571B / period=FY2026_Q2; NVDA_SEC_shares_diluted_FY2026_Q2_0001045810-25-000209 / SEC_0001045810_0001045810-25-000209 / sec_filing / value=24.532B / period=FY2026_Q2; NVDA_SEC_shares_diluted_FY2026_Q3_0001045810-25-000230 / SEC_0001045810_0001045810-25-000230 / sec_filing / value=24.542B / period=FY2026_Q3
- `debt`: NVDA_SEC_COMPANYFACTS_1045810_DEBT / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=n/a / period=None; NVDA_SEC_COMPANYFACTS_1045810_TOTAL_DEBT / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=n/a / period=None
- `cash`: NVDA_SEC_COMPANYFACTS_1045810_CASH_AND_EQUIVALENTS / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=9.107B / period=None; NVDA_SEC_COMPANYFACTS_1045810_CASH_AND_INVESTMENTS / NVDA_SEC_COMPANYFACTS_1045810 / sec_filing / value=58.229B / period=None; NVDA_SEC_cash_and_equivalents_FY2026_FY_0001045810-26-000021 / SEC_0001045810_0001045810-26-000021 / sec_filing / value=10.605B / period=FY2026_FY; NVDA_SEC_cash_and_equivalents_FY2026_Q2_0001045810-25-000209 / SEC_0001045810_0001045810-25-000209 / sec_filing / value=11.639B / period=FY2026_Q2

### AMD

- Verdict: `true_anomaly`
- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`
- Market cap: `581.205B`
- Enterprise value: `577.092B`
- Revenue TTM: `6.413B`
- FCF TTM: `1.813B`
- SBC TTM: `1.415B`
- Shares used: `1.636B`
- Price used: `355.26`
- EV/Sales: `89.99x`
- P/FCF: `320.58x`
- FCF margin: `28.3%`
- SBC/Revenue: `22.1%`
- Fix recommendation: P/FCF is extremely high even without other period red flags; keep as valuation-risk manual review unless FCF source/period is proven wrong.

Evidence IDs / Source IDs:
- `revenue`: AMD_SEC_COMPANYFACTS_2488_REVENUE_TTM / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=6.413B / period=None; AMD_SEC_revenue_FY2025_FY_0000002488-26-000018 / SEC_0000002488_0000002488-26-000018 / sec_filing / value=34.639B / period=FY2025_FY; AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108 / SEC_0000002488_0000002488-25-000108 / sec_filing / value=15.123B / period=FY2025_Q2; AMD_SEC_revenue_FY2025_Q2_0000002488-25-000108 / SEC_0000002488_0000002488-25-000108 / sec_filing / value=7.685B / period=FY2025_Q2
- `fcf`: AMD_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0000002488_DERIVED_FCF / sec_filing / value=8.854B / period=TTM; AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW_TTM / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=1.813B / period=None; AMD_SEC_COMPANYFACTS_2488_FCF / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=n/a / period=None; AMD_SEC_COMPANYFACTS_2488_FREE_CASH_FLOW / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=n/a / period=None
- `sbc`: AMD_SEC_DERIVED_SBC_TO_REVENUE / SEC_0000002488_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.06 / period=TTM; AMD_SEC_COMPANYFACTS_2488_SBC_TO_REVENUE / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=0.22 / period=None; AMD_SEC_COMPANYFACTS_2488_SBC_TTM / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=1.415B / period=None; AMD_SEC_sbc_FY2025_FY_0000002488-26-000018 / SEC_0000002488_0000002488-26-000018 / sec_filing / value=1.638B / period=FY2025_FY
- `shares`: AMD_SEC_shares_diluted_FY2025_FY_0000002488-26-000018 / SEC_0000002488_0000002488-26-000018 / sec_filing / value=1.636B / period=FY2025_FY; AMD_SEC_shares_diluted_FY2025_Q2_0000002488-25-000108 / SEC_0000002488_0000002488-25-000108 / sec_filing / value=1.628B / period=FY2025_Q2; AMD_SEC_shares_diluted_FY2025_Q2_0000002488-25-000108 / SEC_0000002488_0000002488-25-000108 / sec_filing / value=1.630B / period=FY2025_Q2; AMD_SEC_shares_diluted_FY2025_Q3_0000002488-25-000166 / SEC_0000002488_0000002488-25-000166 / sec_filing / value=1.632B / period=FY2025_Q3
- `debt`: AMD_SEC_COMPANYFACTS_2488_DEBT / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=n/a / period=None; AMD_SEC_COMPANYFACTS_2488_TOTAL_DEBT / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=n/a / period=None
- `cash`: AMD_SEC_COMPANYFACTS_2488_CASH_AND_EQUIVALENTS / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=4.113B / period=None; AMD_SEC_COMPANYFACTS_2488_CASH_AND_INVESTMENTS / AMD_SEC_COMPANYFACTS_2488 / sec_filing / value=4.113B / period=None; AMD_SEC_cash_and_equivalents_FY2025_FY_0000002488-26-000018 / SEC_0000002488_0000002488-26-000018 / sec_filing / value=5.556B / period=FY2025_FY; AMD_SEC_cash_and_equivalents_FY2025_Q1_0000002488-25-000047 / SEC_0000002488_0000002488-25-000047 / sec_filing / value=6.059B / period=FY2025_Q1

### MU

- Verdict: `guard_too_strict`
- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`
- Market cap: `731.108B`
- Enterprise value: `723.545B`
- Revenue TTM: `28.089B`
- FCF TTM: `2.703B`
- SBC TTM: `918.000M`
- Shares used: `1.142B`
- Price used: `640.20`
- EV/Sales: `25.76x`
- P/FCF: `270.48x`
- FCF margin: `9.6%`
- SBC/Revenue: `3.3%`
- Fix recommendation: P/FCF is above hard threshold but could be a growth/semiconductor/software context issue; consider sector-aware warning band after validating FCF period.

Evidence IDs / Source IDs:
- `revenue`: MU_SEC_COMPANYFACTS_723125_REVENUE_TTM / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=28.089B / period=None; MU_SEC_revenue_FY2025_FY_0000723125-25-000028 / SEC_0000723125_0000723125-25-000028 / sec_filing / value=37.378B / period=FY2025_FY; MU_SEC_revenue_FY2025_Q3_0000723125-25-000021 / SEC_0000723125_0000723125-25-000021 / sec_filing / value=9.301B / period=FY2025_Q3; MU_SEC_revenue_FY2026_Q1_0000723125-25-000046 / SEC_0000723125_0000723125-25-000046 / sec_filing / value=13.643B / period=FY2026_Q1
- `fcf`: MU_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0000723125_DERIVED_FCF / sec_filing / value=13.081B / period=TTM; MU_SEC_COMPANYFACTS_723125_FREE_CASH_FLOW_TTM / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=2.703B / period=None; MU_SEC_COMPANYFACTS_723125_FCF / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=n/a / period=None; MU_SEC_COMPANYFACTS_723125_FREE_CASH_FLOW / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=n/a / period=None
- `sbc`: MU_SEC_DERIVED_SBC_TO_REVENUE / SEC_0000723125_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.02 / period=TTM; MU_SEC_COMPANYFACTS_723125_SBC_TO_REVENUE / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=0.03 / period=None; MU_SEC_COMPANYFACTS_723125_SBC_TTM / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=918.000M / period=None; MU_SEC_sbc_FY2025_FY_0000723125-25-000028 / SEC_0000723125_0000723125-25-000028 / sec_filing / value=972.000M / period=FY2025_FY
- `shares`: MU_SEC_shares_diluted_FY2025_FY_0000723125-25-000028 / SEC_0000723125_0000723125-25-000028 / sec_filing / value=1.125B / period=FY2025_FY; MU_SEC_shares_diluted_FY2025_Q3_0000723125-25-000021 / SEC_0000723125_0000723125-25-000021 / sec_filing / value=1.125B / period=FY2025_Q3; MU_SEC_shares_diluted_FY2026_Q1_0000723125-25-000046 / SEC_0000723125_0000723125-25-000046 / sec_filing / value=1.138B / period=FY2026_Q1; MU_SEC_shares_diluted_FY2026_Q2_0000723125-26-000006 / SEC_0000723125_0000723125-26-000006 / sec_filing / value=1.140B / period=FY2026_Q2
- `debt`: MU_SEC_COMPANYFACTS_723125_DEBT / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=n/a / period=None; MU_SEC_COMPANYFACTS_723125_TOTAL_DEBT / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=n/a / period=None
- `cash`: MU_SEC_COMPANYFACTS_723125_CASH_AND_EQUIVALENTS / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=7.563B / period=None; MU_SEC_COMPANYFACTS_723125_CASH_AND_INVESTMENTS / MU_SEC_COMPANYFACTS_723125 / sec_filing / value=7.563B / period=None; MU_SEC_cash_and_equivalents_FY2025_FY_0000723125-25-000028 / SEC_0000723125_0000723125-25-000028 / sec_filing / value=9.646B / period=FY2025_FY; MU_SEC_cash_and_equivalents_FY2026_Q1_0000723125-25-000046 / SEC_0000723125_0000723125-25-000046 / sec_filing / value=9.731B / period=FY2026_Q1

### MRVL

- Verdict: `guard_too_strict`
- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`
- Market cap: `146.762B`
- Enterprise value: `145.894B`
- Revenue TTM: `7.492B`
- FCF TTM: `788.700M`
- SBC TTM: `558.300M`
- Shares used: `869.700M`
- Price used: `168.75`
- EV/Sales: `19.47x`
- P/FCF: `186.08x`
- FCF margin: `10.5%`
- SBC/Revenue: `7.5%`
- Fix recommendation: P/FCF is above hard threshold but could be a growth/semiconductor/software context issue; consider sector-aware warning band after validating FCF period.

Evidence IDs / Source IDs:
- `revenue`: MRVL_SEC_COMPANYFACTS_1835632_REVENUE_TTM / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=7.492B / period=None; MRVL_SEC_revenue_FY2026_FY_0001835632-26-000011 / SEC_0001835632_0001835632-26-000011 / sec_filing / value=8.195B / period=FY2026_FY; MRVL_SEC_revenue_FY2026_Q2_0001835632-25-000189 / SEC_0001835632_0001835632-25-000189 / sec_filing / value=3.901B / period=FY2026_Q2; MRVL_SEC_revenue_FY2026_Q2_0001835632-25-000189 / SEC_0001835632_0001835632-25-000189 / sec_filing / value=2.006B / period=FY2026_Q2
- `fcf`: MRVL_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001835632_DERIVED_FCF / sec_filing / value=2.932B / period=TTM; MRVL_SEC_COMPANYFACTS_1835632_FREE_CASH_FLOW_TTM / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=788.700M / period=None; MRVL_SEC_COMPANYFACTS_1835632_FCF / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=n/a / period=None; MRVL_SEC_COMPANYFACTS_1835632_FREE_CASH_FLOW / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=n/a / period=None
- `sbc`: MRVL_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001835632_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.10 / period=TTM; MRVL_SEC_COMPANYFACTS_1835632_SBC_TO_REVENUE / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=0.07 / period=None; MRVL_SEC_COMPANYFACTS_1835632_SBC_TTM / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=558.300M / period=None; MRVL_SEC_sbc_FY2026_FY_0001835632-26-000011 / SEC_0001835632_0001835632-26-000011 / sec_filing / value=590.800M / period=FY2026_FY
- `shares`: MRVL_SEC_shares_diluted_FY2026_FY_0001835632-26-000011 / SEC_0001835632_0001835632-26-000011 / sec_filing / value=869.700M / period=FY2026_FY; MRVL_SEC_shares_diluted_FY2026_Q2_0001835632-25-000189 / SEC_0001835632_0001835632-25-000189 / sec_filing / value=873.000M / period=FY2026_Q2; MRVL_SEC_shares_diluted_FY2026_Q2_0001835632-25-000189 / SEC_0001835632_0001835632-25-000189 / sec_filing / value=870.400M / period=FY2026_Q2; MRVL_SEC_shares_diluted_FY2026_Q3_0001835632-25-000197 / SEC_0001835632_0001835632-25-000197 / sec_filing / value=869.900M / period=FY2026_Q3
- `debt`: MRVL_SEC_COMPANYFACTS_1835632_DEBT / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=n/a / period=None; MRVL_SEC_COMPANYFACTS_1835632_TOTAL_DEBT / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=n/a / period=None
- `cash`: MRVL_SEC_COMPANYFACTS_1835632_CASH_AND_EQUIVALENTS / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=868.100M / period=None; MRVL_SEC_COMPANYFACTS_1835632_CASH_AND_INVESTMENTS / MRVL_SEC_COMPANYFACTS_1835632 / sec_filing / value=868.100M / period=None; MRVL_SEC_cash_and_equivalents_FY2026_FY_0001835632-26-000011 / SEC_0001835632_0001835632-26-000011 / sec_filing / value=2.639B / period=FY2026_FY; MRVL_SEC_cash_and_equivalents_FY2026_Q2_0001835632-25-000189 / SEC_0001835632_0001835632-25-000189 / sec_filing / value=1.224B / period=FY2026_Q2

### ANET

- Verdict: `period_bug`
- Manual-review reason codes: `FINANCIAL_SANITY_EV_SALES_ABSURD, FINANCIAL_SANITY_FCF_MARGIN_ANOMALY, FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`
- Market cap: `217.150B`
- Enterprise value: `213.973B`
- Revenue TTM: `1.816B`
- FCF TTM: `1.991B`
- SBC TTM: `310.296M`
- Shares used: `1.276B`
- Price used: `170.22`
- EV/Sales: `117.85x`
- P/FCF: `109.07x`
- FCF margin: `109.7%`
- SBC/Revenue: `17.1%`
- Fix recommendation: Revenue denominator is likely not a true TTM/annual comparable period; rerun PeriodResolver for annual vs quarterly/YTD facts and only derive TTM from four comparable duration facts.

Evidence IDs / Source IDs:
- `revenue`: ANET_SEC_COMPANYFACTS_1596532_REVENUE_TTM / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=1.816B / period=None; ANET_SEC_revenue_FY2025_FY_0001596532-26-000013 / SEC_0001596532_0001596532-26-000013 / sec_filing / value=9.006B / period=FY2025_FY; ANET_SEC_revenue_FY2025_Q2_0001596532-25-000216 / SEC_0001596532_0001596532-25-000216 / sec_filing / value=4.210B / period=FY2025_Q2; ANET_SEC_revenue_FY2025_Q2_0001596532-25-000216 / SEC_0001596532_0001596532-25-000216 / sec_filing / value=2.205B / period=FY2025_Q2
- `fcf`: ANET_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001596532_DERIVED_FCF / sec_filing / value=8.088B / period=TTM; ANET_SEC_COMPANYFACTS_1596532_FREE_CASH_FLOW_TTM / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=1.991B / period=None; ANET_SEC_COMPANYFACTS_1596532_FCF / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=n/a / period=None; ANET_SEC_COMPANYFACTS_1596532_FREE_CASH_FLOW / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=n/a / period=None
- `sbc`: ANET_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001596532_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.05 / period=TTM; ANET_SEC_COMPANYFACTS_1596532_SBC_TO_REVENUE / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=0.17 / period=None; ANET_SEC_COMPANYFACTS_1596532_SBC_TTM / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=310.296M / period=None; ANET_SEC_sbc_FY2025_FY_0001596532-26-000013 / SEC_0001596532_0001596532-26-000013 / sec_filing / value=439.200M / period=FY2025_FY
- `shares`: ANET_SEC_shares_diluted_FY2025_FY_0001596532-26-000013 / SEC_0001596532_0001596532-26-000013 / sec_filing / value=1.276B / period=FY2025_FY; ANET_SEC_shares_diluted_FY2025_Q2_0001596532-25-000216 / SEC_0001596532_0001596532-25-000216 / sec_filing / value=1.275B / period=FY2025_Q2; ANET_SEC_shares_diluted_FY2025_Q2_0001596532-25-000216 / SEC_0001596532_0001596532-25-000216 / sec_filing / value=1.271B / period=FY2025_Q2; ANET_SEC_shares_diluted_FY2025_Q3_0001596532-25-000286 / SEC_0001596532_0001596532-25-000286 / sec_filing / value=1.276B / period=FY2025_Q3
- `debt`: ANET_SEC_COMPANYFACTS_1596532_DEBT / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=n/a / period=None; ANET_SEC_COMPANYFACTS_1596532_TOTAL_DEBT / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=n/a / period=None
- `cash`: ANET_SEC_COMPANYFACTS_1596532_CASH_AND_EQUIVALENTS / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=3.176B / period=None; ANET_SEC_COMPANYFACTS_1596532_CASH_AND_INVESTMENTS / ANET_SEC_COMPANYFACTS_1596532 / sec_filing / value=3.176B / period=None; ANET_SEC_cash_and_equivalents_FY2025_FY_0001596532-26-000013 / SEC_0001596532_0001596532-26-000013 / sec_filing / value=1.965B / period=FY2025_FY; ANET_SEC_cash_and_equivalents_FY2025_Q2_0001596532-25-000216 / SEC_0001596532_0001596532-25-000216 / sec_filing / value=2.225B / period=FY2025_Q2

### MDB

- Verdict: `period_bug`
- Manual-review reason codes: `FINANCIAL_SANITY_EV_SALES_ABSURD`
- Market cap: `21.667B`
- Enterprise value: `21.210B`
- Revenue TTM: `182.800M`
- FCF TTM: `287.573M`
- SBC TTM: `477.912M`
- Shares used: `81.247M`
- Price used: `266.68`
- EV/Sales: `116.03x`
- P/FCF: `75.34x`
- FCF margin: `157.3%`
- SBC/Revenue: `261.4%`
- Fix recommendation: Revenue denominator is likely not a true TTM/annual comparable period; rerun PeriodResolver for annual vs quarterly/YTD facts and only derive TTM from four comparable duration facts.

Evidence IDs / Source IDs:
- `revenue`: MDB_SEC_COMPANYFACTS_1441816_REVENUE_TTM / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=182.800M / period=None; MDB_SEC_revenue_FY2026_FY_0001628280-26-016799 / SEC_0001441816_0001628280-26-016799 / sec_filing / value=2.464B / period=FY2026_FY; MDB_SEC_revenue_FY2026_Q2_0001441816-25-000181 / SEC_0001441816_0001441816-25-000181 / sec_filing / value=1.140B / period=FY2026_Q2; MDB_SEC_revenue_FY2026_Q2_0001441816-25-000181 / SEC_0001441816_0001441816-25-000181 / sec_filing / value=591.402M / period=FY2026_Q2
- `fcf`: MDB_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001441816_DERIVED_FCF / sec_filing / value=706.004M / period=TTM; MDB_SEC_COMPANYFACTS_1441816_FREE_CASH_FLOW_TTM / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=287.573M / period=None; MDB_SEC_COMPANYFACTS_1441816_FCF / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=n/a / period=None; MDB_SEC_COMPANYFACTS_1441816_FREE_CASH_FLOW / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=n/a / period=None
- `sbc`: MDB_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001441816_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.29 / period=TTM; MDB_SEC_COMPANYFACTS_1441816_SBC_TO_REVENUE / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=2.61 / period=None; MDB_SEC_COMPANYFACTS_1441816_SBC_TTM / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=477.912M / period=None; MDB_SEC_sbc_FY2026_FY_0001628280-26-016799 / SEC_0001441816_0001628280-26-016799 / sec_filing / value=550.454M / period=FY2026_FY
- `shares`: MDB_SEC_shares_diluted_FY2026_FY_0001628280-26-016799 / SEC_0001441816_0001628280-26-016799 / sec_filing / value=81.247M / period=FY2026_FY; MDB_SEC_COMPANYFACTS_1441816_SHARES / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=n/a / period=None
- `debt`: MDB_SEC_COMPANYFACTS_1441816_DEBT / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=n/a / period=None; MDB_SEC_COMPANYFACTS_1441816_TOTAL_DEBT / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=n/a / period=None
- `cash`: MDB_SEC_COMPANYFACTS_1441816_CASH_AND_EQUIVALENTS / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=456.339M / period=None; MDB_SEC_COMPANYFACTS_1441816_CASH_AND_INVESTMENTS / MDB_SEC_COMPANYFACTS_1441816 / sec_filing / value=456.339M / period=None; MDB_SEC_cash_and_equivalents_FY2026_FY_0001628280-26-016799 / SEC_0001441816_0001628280-26-016799 / sec_filing / value=1.087B / period=FY2026_FY; MDB_SEC_cash_and_equivalents_FY2026_Q2_0001441816-25-000181 / SEC_0001441816_0001441816-25-000181 / sec_filing / value=647.139M / period=FY2026_Q2

### CRWD

- Verdict: `guard_too_strict`
- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`
- Market cap: `119.407B`
- Enterprise value: `116.303B`
- Revenue TTM: `n/a`
- FCF TTM: `1.109B`
- SBC TTM: `698.441M`
- Shares used: `250.576M`
- Price used: `476.53`
- EV/Sales: `n/a`
- P/FCF: `107.66x`
- FCF margin: `n/a`
- SBC/Revenue: `n/a`
- Fix recommendation: P/FCF is above hard threshold but could be a growth/semiconductor/software context issue; consider sector-aware warning band after validating FCF period.

Evidence IDs / Source IDs:
- `revenue`: CRWD_SEC_COMPANYFACTS_1535527_REVENUE / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=n/a / period=None; CRWD_SEC_COMPANYFACTS_1535527_REVENUE_TTM / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=n/a / period=None; CRWD_SEC_COMPANYFACTS_1535527_SALES / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=n/a / period=None
- `fcf`: CRWD_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001535527_DERIVED_FCF / sec_filing / value=2.682B / period=TTM; CRWD_SEC_COMPANYFACTS_1535527_FREE_CASH_FLOW_TTM / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=1.109B / period=None; CRWD_SEC_COMPANYFACTS_1535527_FCF / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=n/a / period=None; CRWD_SEC_COMPANYFACTS_1535527_FREE_CASH_FLOW / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=n/a / period=None
- `sbc`: CRWD_SEC_COMPANYFACTS_1535527_SBC_TTM / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=698.441M / period=None; CRWD_SEC_sbc_FY2025_Q1_0001535527-25-000019 / SEC_0001535527_0001535527-25-000019 / sec_filing / value=253.604M / period=FY2025_Q1; CRWD_SEC_sbc_FY2026_FY_0001535527-26-000010 / SEC_0001535527_0001535527-26-000010 / sec_filing / value=1.097B / period=FY2026_FY; CRWD_SEC_sbc_FY2026_Q2_0001535527-25-000025 / SEC_0001535527_0001535527-25-000025 / sec_filing / value=540.757M / period=FY2026_Q2
- `shares`: CRWD_SEC_shares_diluted_FY2026_FY_0001535527-26-000010 / SEC_0001535527_0001535527-26-000010 / sec_filing / value=250.576M / period=FY2026_FY; CRWD_SEC_shares_diluted_FY2026_Q2_0001535527-25-000025 / SEC_0001535527_0001535527-25-000025 / sec_filing / value=249.182M / period=FY2026_Q2; CRWD_SEC_shares_diluted_FY2026_Q2_0001535527-25-000025 / SEC_0001535527_0001535527-25-000025 / sec_filing / value=249.909M / period=FY2026_Q2; CRWD_SEC_shares_diluted_FY2026_Q3_0001535527-25-000033 / SEC_0001535527_0001535527-25-000033 / sec_filing / value=249.905M / period=FY2026_Q3
- `debt`: CRWD_SEC_COMPANYFACTS_1535527_DEBT / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=n/a / period=None; CRWD_SEC_COMPANYFACTS_1535527_TOTAL_DEBT / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=n/a / period=None
- `cash`: CRWD_SEC_COMPANYFACTS_1535527_CASH_AND_EQUIVALENTS / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=2.457B / period=None; CRWD_SEC_COMPANYFACTS_1535527_CASH_AND_INVESTMENTS / CRWD_SEC_COMPANYFACTS_1535527 / sec_filing / value=3.104B / period=None; CRWD_SEC_cash_and_equivalents_FY2026_FY_0001535527-26-000010 / SEC_0001535527_0001535527-26-000010 / sec_filing / value=5.315B / period=FY2026_FY; CRWD_SEC_cash_and_equivalents_FY2026_Q2_0001535527-25-000025 / SEC_0001535527_0001535527-25-000025 / sec_filing / value=4.972B / period=FY2026_Q2

### NET

- Verdict: `true_anomaly`
- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`
- Market cap: `85.165B`
- Enterprise value: `84.979B`
- Revenue TTM: `1.984B`
- FCF TTM: `161.814M`
- SBC TTM: `292.382M`
- Shares used: `348.421M`
- Price used: `244.43`
- EV/Sales: `42.84x`
- P/FCF: `526.31x`
- FCF margin: `8.2%`
- SBC/Revenue: `14.7%`
- Fix recommendation: P/FCF is extremely high even without other period red flags; keep as valuation-risk manual review unless FCF source/period is proven wrong.

Evidence IDs / Source IDs:
- `revenue`: NET_SEC_COMPANYFACTS_1477333_REVENUE_TTM / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=1.984B / period=None; NET_SEC_revenue_FY2025_FY_0001477333-26-000016 / SEC_0001477333_0001477333-26-000016 / sec_filing / value=2.168B / period=FY2025_FY; NET_SEC_revenue_FY2025_Q2_0001477333-25-000137 / SEC_0001477333_0001477333-25-000137 / sec_filing / value=991.403M / period=FY2025_Q2; NET_SEC_revenue_FY2025_Q2_0001477333-25-000137 / SEC_0001477333_0001477333-25-000137 / sec_filing / value=512.316M / period=FY2025_Q2
- `fcf`: NET_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001477333_DERIVED_FCF / sec_filing / value=483.202M / period=TTM; NET_SEC_COMPANYFACTS_1477333_FREE_CASH_FLOW_TTM / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=161.814M / period=None; NET_SEC_COMPANYFACTS_1477333_FCF / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=n/a / period=None; NET_SEC_COMPANYFACTS_1477333_FREE_CASH_FLOW / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=n/a / period=None
- `sbc`: NET_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001477333_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.24 / period=TTM; NET_SEC_COMPANYFACTS_1477333_SBC_TO_REVENUE / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=0.15 / period=None; NET_SEC_COMPANYFACTS_1477333_SBC_TTM / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=292.382M / period=None; NET_SEC_sbc_FY2025_FY_0001477333-26-000016 / SEC_0001477333_0001477333-26-000016 / sec_filing / value=451.454M / period=FY2025_FY
- `shares`: NET_SEC_shares_diluted_FY2025_FY_0001477333-26-000016 / SEC_0001477333_0001477333-26-000016 / sec_filing / value=348.421M / period=FY2025_FY; NET_SEC_shares_diluted_FY2025_Q2_0001477333-25-000137 / SEC_0001477333_0001477333-25-000137 / sec_filing / value=346.605M / period=FY2025_Q2; NET_SEC_shares_diluted_FY2025_Q2_0001477333-25-000137 / SEC_0001477333_0001477333-25-000137 / sec_filing / value=347.489M / period=FY2025_Q2; NET_SEC_shares_diluted_FY2025_Q3_0001477333-25-000141 / SEC_0001477333_0001477333-25-000141 / sec_filing / value=347.519M / period=FY2025_Q3
- `debt`: NET_SEC_COMPANYFACTS_1477333_DEBT / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=n/a / period=None; NET_SEC_COMPANYFACTS_1477333_TOTAL_DEBT / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=n/a / period=None
- `cash`: NET_SEC_COMPANYFACTS_1477333_CASH_AND_EQUIVALENTS / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=185.906M / period=None; NET_SEC_COMPANYFACTS_1477333_CASH_AND_INVESTMENTS / NET_SEC_COMPANYFACTS_1477333 / sec_filing / value=185.906M / period=None; NET_SEC_cash_and_equivalents_FY2025_FY_0001477333-26-000016 / SEC_0001477333_0001477333-26-000016 / sec_filing / value=954.357M / period=FY2025_FY; NET_SEC_cash_and_equivalents_FY2025_Q2_0001477333-25-000137 / SEC_0001477333_0001477333-25-000137 / sec_filing / value=1.519B / period=FY2025_Q2

### PANW

- Verdict: `guard_too_strict`
- Manual-review reason codes: `FINANCIAL_SANITY_SBC_REVENUE_ANOMALY`
- Market cap: `130.810B`
- Enterprise value: `128.885B`
- Revenue TTM: `2.335B`
- FCF TTM: `n/a`
- SBC TTM: `1.230B`
- Shares used: `711.000M`
- Price used: `183.98`
- EV/Sales: `55.20x`
- P/FCF: `n/a`
- FCF margin: `n/a`
- SBC/Revenue: `52.7%`
- Fix recommendation: SBC/Revenue guard fired near software profile boundaries; verify revenue period first, then either add sector context or keep manual review if ratio remains above 30%.

Evidence IDs / Source IDs:
- `revenue`: PANW_SEC_COMPANYFACTS_1327567_REVENUE_TTM / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=2.335B / period=None; PANW_SEC_revenue_FY2025_FY_0001327567-25-000027 / SEC_0001327567_0001327567-25-000027 / sec_filing / value=9.222B / period=FY2025_FY; PANW_SEC_revenue_FY2025_Q3_0001327567-25-000017 / SEC_0001327567_0001327567-25-000017 / sec_filing / value=2.289B / period=FY2025_Q3; PANW_SEC_revenue_FY2026_Q1_0001327567-25-000035 / SEC_0001327567_0001327567-25-000035 / sec_filing / value=2.474B / period=FY2026_Q1
- `fcf`: PANW_SEC_COMPANYFACTS_1327567_FCF / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=n/a / period=None; PANW_SEC_COMPANYFACTS_1327567_FREE_CASH_FLOW / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=n/a / period=None; PANW_SEC_COMPANYFACTS_1327567_FREE_CASH_FLOW_TTM / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=n/a / period=None
- `sbc`: PANW_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001327567_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.21 / period=TTM; PANW_SEC_COMPANYFACTS_1327567_SBC_TO_REVENUE / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=0.53 / period=None; PANW_SEC_COMPANYFACTS_1327567_SBC_TTM / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=1.230B / period=None; PANW_SEC_sbc_FY2025_FY_0001327567-25-000027 / SEC_0001327567_0001327567-25-000027 / sec_filing / value=1.295B / period=FY2025_FY
- `shares`: PANW_SEC_shares_diluted_FY2025_FY_0001327567-25-000027 / SEC_0001327567_0001327567-25-000027 / sec_filing / value=709.300M / period=FY2025_FY; PANW_SEC_shares_diluted_FY2025_Q3_0001327567-25-000017 / SEC_0001327567_0001327567-25-000017 / sec_filing / value=707.400M / period=FY2025_Q3; PANW_SEC_shares_diluted_FY2026_Q1_0001327567-25-000035 / SEC_0001327567_0001327567-25-000035 / sec_filing / value=709.000M / period=FY2026_Q1; PANW_SEC_shares_diluted_FY2026_Q2_0001327567-26-000005 / SEC_0001327567_0001327567-26-000005 / sec_filing / value=713.000M / period=FY2026_Q2
- `debt`: PANW_SEC_COMPANYFACTS_1327567_DEBT / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=n/a / period=None; PANW_SEC_COMPANYFACTS_1327567_TOTAL_DEBT / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=n/a / period=None
- `cash`: PANW_SEC_COMPANYFACTS_1327567_CASH_AND_EQUIVALENTS / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=1.547B / period=None; PANW_SEC_COMPANYFACTS_1327567_CASH_AND_INVESTMENTS / PANW_SEC_COMPANYFACTS_1327567 / sec_filing / value=1.925B / period=None; PANW_SEC_cash_and_equivalents_FY2025_FY_0001327567-25-000027 / SEC_0001327567_0001327567-25-000027 / sec_filing / value=2.279B / period=FY2025_FY; PANW_SEC_cash_and_equivalents_FY2026_Q1_0001327567-25-000035 / SEC_0001327567_0001327567-25-000035 / sec_filing / value=3.066B / period=FY2026_Q1

### NOW

- Verdict: `period_bug`
- Manual-review reason codes: `FINANCIAL_SANITY_EV_SALES_ABSURD, FINANCIAL_SANITY_FCF_MARGIN_ANOMALY, FINANCIAL_SANITY_SBC_REVENUE_ANOMALY`
- Market cap: `95.680B`
- Enterprise value: `93.370B`
- Revenue TTM: `309.280M`
- FCF TTM: `5.679B`
- SBC TTM: `1.909B`
- Shares used: `1.040B`
- Price used: `92.01`
- EV/Sales: `301.89x`
- P/FCF: `16.85x`
- FCF margin: `1836.2%`
- SBC/Revenue: `617.2%`
- Fix recommendation: Revenue denominator is likely not a true TTM/annual comparable period; rerun PeriodResolver for annual vs quarterly/YTD facts and only derive TTM from four comparable duration facts.

Evidence IDs / Source IDs:
- `revenue`: NOW_SEC_COMPANYFACTS_1373715_REVENUE_TTM / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=309.280M / period=None; NOW_SEC_revenue_FY2025_FY_0001373715-26-000007 / SEC_0001373715_0001373715-26-000007 / sec_filing / value=13.278B / period=FY2025_FY; NOW_SEC_revenue_FY2025_Q2_0001373715-25-000276 / SEC_0001373715_0001373715-25-000276 / sec_filing / value=3.215B / period=FY2025_Q2; NOW_SEC_revenue_FY2025_Q3_0001373715-25-000309 / SEC_0001373715_0001373715-25-000309 / sec_filing / value=9.710B / period=FY2025_Q3
- `fcf`: NOW_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001373715_DERIVED_FCF / sec_filing / value=7.575B / period=TTM; NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW_TTM / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=5.679B / period=None; NOW_SEC_COMPANYFACTS_1373715_FCF / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=n/a / period=None; NOW_SEC_COMPANYFACTS_1373715_FREE_CASH_FLOW / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=n/a / period=None
- `sbc`: NOW_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001373715_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.17 / period=TTM; NOW_SEC_COMPANYFACTS_1373715_SBC_TO_REVENUE / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=6.17 / period=None; NOW_SEC_COMPANYFACTS_1373715_SBC_TTM / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=1.909B / period=None; NOW_SEC_sbc_FY2025_FY_0001373715-26-000007 / SEC_0001373715_0001373715-26-000007 / sec_filing / value=1.955B / period=FY2025_FY
- `shares`: NOW_SEC_shares_diluted_FY2025_FY_0001373715-26-000007 / SEC_0001373715_0001373715-26-000007 / sec_filing / value=1.047B / period=FY2025_FY; NOW_SEC_shares_diluted_FY2025_Q2_0001373715-25-000276 / SEC_0001373715_0001373715-25-000276 / sec_filing / value=209.322M / period=FY2025_Q2; NOW_SEC_shares_diluted_FY2025_Q3_0001373715-25-000309 / SEC_0001373715_0001373715-25-000309 / sec_filing / value=209.370M / period=FY2025_Q3; NOW_SEC_shares_diluted_FY2025_Q3_0001373715-25-000309 / SEC_0001373715_0001373715-25-000309 / sec_filing / value=209.505M / period=FY2025_Q3
- `debt`: NOW_SEC_COMPANYFACTS_1373715_DEBT / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=n/a / period=None; NOW_SEC_COMPANYFACTS_1373715_TOTAL_DEBT / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=n/a / period=None
- `cash`: NOW_SEC_COMPANYFACTS_1373715_CASH_AND_EQUIVALENTS / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=2.310B / period=None; NOW_SEC_COMPANYFACTS_1373715_CASH_AND_INVESTMENTS / NOW_SEC_COMPANYFACTS_1373715 / sec_filing / value=2.310B / period=None; NOW_SEC_cash_and_equivalents_FY2025_FY_0001373715-26-000007 / SEC_0001373715_0001373715-26-000007 / sec_filing / value=3.732B / period=FY2025_FY; NOW_SEC_cash_and_equivalents_FY2026_Q1_0001373715-26-000056 / SEC_0001373715_0001373715-26-000056 / sec_filing / value=3.726B / period=FY2026_Q1

### INTU

- Verdict: `guard_too_strict`
- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY, FINANCIAL_SANITY_SBC_REVENUE_ANOMALY`
- Market cap: `111.530B`
- Enterprise value: `104.431B`
- Revenue TTM: `5.818B`
- FCF TTM: `1.076B`
- SBC TTM: `2.031B`
- Shares used: `280.000M`
- Price used: `398.32`
- EV/Sales: `17.95x`
- P/FCF: `103.65x`
- FCF margin: `18.5%`
- SBC/Revenue: `34.9%`
- Fix recommendation: SBC/Revenue guard fired near software profile boundaries; verify revenue period first, then either add sector context or keep manual review if ratio remains above 30%.

Evidence IDs / Source IDs:
- `revenue`: INTU_SEC_COMPANYFACTS_896878_REVENUE_TTM / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=5.818B / period=None; INTU_SEC_revenue_FY2025_FY_0000896878-25-000035 / SEC_0000896878_0000896878-25-000035 / sec_filing / value=18.831B / period=FY2025_FY; INTU_SEC_revenue_FY2026_Q2_0000896878-26-000014 / SEC_0000896878_0000896878-26-000014 / sec_filing / value=8.536B / period=FY2026_Q2; INTU_SEC_revenue_FY2026_Q2_0000896878-26-000014 / SEC_0000896878_0000896878-26-000014 / sec_filing / value=4.651B / period=FY2026_Q2
- `fcf`: INTU_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0000896878_DERIVED_FCF / sec_filing / value=9.816B / period=TTM; INTU_SEC_COMPANYFACTS_896878_FREE_CASH_FLOW_TTM / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=1.076B / period=None; INTU_SEC_COMPANYFACTS_896878_FCF / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=n/a / period=None; INTU_SEC_COMPANYFACTS_896878_FREE_CASH_FLOW / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=n/a / period=None
- `sbc`: INTU_SEC_DERIVED_SBC_TO_REVENUE / SEC_0000896878_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.10 / period=TTM; INTU_SEC_COMPANYFACTS_896878_SBC_TO_REVENUE / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=0.35 / period=None; INTU_SEC_COMPANYFACTS_896878_SBC_TTM / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=2.031B / period=None; INTU_SEC_sbc_FY2025_FY_0000896878-25-000035 / SEC_0000896878_0000896878-25-000035 / sec_filing / value=1.968B / period=FY2025_FY
- `shares`: INTU_SEC_shares_diluted_FY2025_FY_0000896878-25-000035 / SEC_0000896878_0000896878-25-000035 / sec_filing / value=283.000M / period=FY2025_FY; INTU_SEC_shares_diluted_FY2025_Q3_0000896878-25-000022 / SEC_0000896878_0000896878-25-000022 / sec_filing / value=282.000M / period=FY2025_Q3; INTU_SEC_shares_diluted_FY2026_Q1_0000896878-25-000048 / SEC_0000896878_0000896878-25-000048 / sec_filing / value=281.000M / period=FY2026_Q1; INTU_SEC_shares_diluted_FY2026_Q2_0000896878-26-000014 / SEC_0000896878_0000896878-26-000014 / sec_filing / value=281.000M / period=FY2026_Q2
- `debt`: INTU_SEC_COMPANYFACTS_896878_DEBT / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=n/a / period=None; INTU_SEC_COMPANYFACTS_896878_TOTAL_DEBT / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=n/a / period=None
- `cash`: INTU_SEC_COMPANYFACTS_896878_CASH_AND_EQUIVALENTS / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=7.099B / period=None; INTU_SEC_COMPANYFACTS_896878_CASH_AND_INVESTMENTS / INTU_SEC_COMPANYFACTS_896878 / sec_filing / value=7.099B / period=None; INTU_SEC_cash_and_equivalents_FY2025_FY_0000896878-25-000035 / SEC_0000896878_0000896878-25-000035 / sec_filing / value=9.481B / period=FY2025_FY; INTU_SEC_cash_and_equivalents_FY2026_Q1_0000896878-25-000048 / SEC_0000896878_0000896878-25-000048 / sec_filing / value=3.506B / period=FY2026_Q1

### UBER

- Verdict: `period_bug`
- Manual-review reason codes: `FINANCIAL_SANITY_FCF_MARGIN_ANOMALY`
- Market cap: `154.631B`
- Enterprise value: `147.426B`
- Revenue TTM: `11.617B`
- FCF TTM: `5.517B`
- SBC TTM: `1.873B`
- Shares used: `2.120B`
- Price used: `72.95`
- EV/Sales: `12.69x`
- P/FCF: `28.03x`
- FCF margin: `47.5%`
- SBC/Revenue: `16.1%`
- Fix recommendation: FCF margin is implausibly high for this profile; prioritize company-defined FCF where available and reconcile revenue/FCF periods before publish.

Evidence IDs / Source IDs:
- `revenue`: UBER_SEC_COMPANYFACTS_1543151_REVENUE_TTM / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=11.617B / period=None; UBER_SEC_revenue_FY2025_FY_0001543151-26-000015 / SEC_0001543151_0001543151-26-000015 / sec_filing / value=52.017B / period=FY2025_FY; UBER_SEC_revenue_FY2025_Q2_0001543151-25-000023 / SEC_0001543151_0001543151-25-000023 / sec_filing / value=24.184B / period=FY2025_Q2; UBER_SEC_revenue_FY2025_Q2_0001543151-25-000023 / SEC_0001543151_0001543151-25-000023 / sec_filing / value=12.651B / period=FY2025_Q2
- `fcf`: UBER_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001543151_DERIVED_FCF / sec_filing / value=19.119B / period=TTM; UBER_SEC_COMPANYFACTS_1543151_FREE_CASH_FLOW_TTM / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=5.517B / period=None; UBER_SEC_COMPANYFACTS_1543151_FCF / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=n/a / period=None; UBER_SEC_COMPANYFACTS_1543151_FREE_CASH_FLOW / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=n/a / period=None
- `sbc`: UBER_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001543151_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.05 / period=TTM; UBER_SEC_COMPANYFACTS_1543151_SBC_TO_REVENUE / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=0.16 / period=None; UBER_SEC_COMPANYFACTS_1543151_SBC_TTM / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=1.873B / period=None; UBER_SEC_sbc_FY2025_FY_0001543151-26-000015 / SEC_0001543151_0001543151-26-000015 / sec_filing / value=1.826B / period=FY2025_FY
- `shares`: UBER_SEC_shares_diluted_FY2025_FY_0001543151-26-000015 / SEC_0001543151_0001543151-26-000015 / sec_filing / value=2.120B / period=FY2025_FY; UBER_SEC_shares_diluted_FY2025_Q2_0001543151-25-000023 / SEC_0001543151_0001543151-25-000023 / sec_filing / value=2.124B / period=FY2025_Q2; UBER_SEC_shares_diluted_FY2025_Q2_0001543151-25-000023 / SEC_0001543151_0001543151-25-000023 / sec_filing / value=2.126B / period=FY2025_Q2; UBER_SEC_shares_diluted_FY2025_Q3_0001543151-25-000033 / SEC_0001543151_0001543151-25-000033 / sec_filing / value=2.124B / period=FY2025_Q3
- `debt`: UBER_SEC_COMPANYFACTS_1543151_DEBT / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=n/a / period=None; UBER_SEC_COMPANYFACTS_1543151_TOTAL_DEBT / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=n/a / period=None
- `cash`: UBER_SEC_COMPANYFACTS_1543151_CASH_AND_EQUIVALENTS / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=6.677B / period=None; UBER_SEC_COMPANYFACTS_1543151_CASH_AND_INVESTMENTS / UBER_SEC_COMPANYFACTS_1543151 / sec_filing / value=7.205B / period=None; UBER_SEC_cash_and_equivalents_FY2025_FY_0001543151-26-000015 / SEC_0001543151_0001543151-26-000015 / sec_filing / value=9.647B / period=FY2025_FY; UBER_SEC_cash_and_equivalents_FY2025_Q2_0001543151-25-000023 / SEC_0001543151_0001543151-25-000023 / sec_filing / value=6.438B / period=FY2025_Q2

### TSLA

- Verdict: `true_anomaly`
- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`
- Market cap: `1377.591B`
- Enterprise value: `1359.413B`
- Revenue TTM: `92.313B`
- FCF TTM: `237.000M`
- SBC TTM: `2.700B`
- Shares used: `3.538B`
- Price used: `389.37`
- EV/Sales: `14.73x`
- P/FCF: `5812.62x`
- FCF margin: `0.3%`
- SBC/Revenue: `2.9%`
- Fix recommendation: P/FCF is extremely high even without other period red flags; keep as valuation-risk manual review unless FCF source/period is proven wrong.

Evidence IDs / Source IDs:
- `revenue`: TSLA_SEC_COMPANYFACTS_1318605_REVENUE_TTM / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=92.313B / period=None; TSLA_SEC_revenue_FY2025_FY_0001628280-26-003952 / SEC_0001318605_0001628280-26-003952 / sec_filing / value=94.827B / period=FY2025_FY; TSLA_SEC_revenue_FY2025_Q3_0001628280-25-045968 / SEC_0001318605_0001628280-25-045968 / sec_filing / value=69.926B / period=FY2025_Q3; TSLA_SEC_revenue_FY2025_Q3_0001628280-25-045968 / SEC_0001318605_0001628280-25-045968 / sec_filing / value=28.095B / period=FY2025_Q3
- `fcf`: TSLA_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001318605_DERIVED_FCF / sec_filing / value=7.718B / period=TTM; TSLA_SEC_COMPANYFACTS_1318605_FREE_CASH_FLOW_TTM / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=237.000M / period=None; TSLA_SEC_COMPANYFACTS_1318605_FCF / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=n/a / period=None; TSLA_SEC_COMPANYFACTS_1318605_FREE_CASH_FLOW / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=n/a / period=None
- `sbc`: TSLA_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001318605_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.03 / period=TTM; TSLA_SEC_COMPANYFACTS_1318605_SBC_TO_REVENUE / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=0.03 / period=None; TSLA_SEC_COMPANYFACTS_1318605_SBC_TTM / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=2.700B / period=None; TSLA_SEC_sbc_FY2025_FY_0001628280-26-003952 / SEC_0001318605_0001628280-26-003952 / sec_filing / value=2.825B / period=FY2025_FY
- `shares`: TSLA_SEC_shares_diluted_FY2025_FY_0001628280-26-003952 / SEC_0001318605_0001628280-26-003952 / sec_filing / value=3.528B / period=FY2025_FY; TSLA_SEC_shares_diluted_FY2025_Q2_0001628280-25-035806 / SEC_0001318605_0001628280-25-035806 / sec_filing / value=3.519B / period=FY2025_Q2; TSLA_SEC_shares_diluted_FY2025_Q3_0001628280-25-045968 / SEC_0001318605_0001628280-25-045968 / sec_filing / value=3.523B / period=FY2025_Q3; TSLA_SEC_shares_diluted_FY2025_Q3_0001628280-25-045968 / SEC_0001318605_0001628280-25-045968 / sec_filing / value=3.526B / period=FY2025_Q3
- `debt`: TSLA_SEC_COMPANYFACTS_1318605_DEBT / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=n/a / period=None; TSLA_SEC_COMPANYFACTS_1318605_TOTAL_DEBT / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=n/a / period=None
- `cash`: TSLA_SEC_COMPANYFACTS_1318605_CASH_AND_EQUIVALENTS / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=16.603B / period=None; TSLA_SEC_COMPANYFACTS_1318605_CASH_AND_INVESTMENTS / TSLA_SEC_COMPANYFACTS_1318605 / sec_filing / value=18.178B / period=None; TSLA_SEC_cash_and_equivalents_FY2025_FY_0001628280-26-003952 / SEC_0001318605_0001628280-26-003952 / sec_filing / value=16.513B / period=FY2025_FY; TSLA_SEC_cash_and_equivalents_FY2025_Q2_0001628280-25-035806 / SEC_0001318605_0001628280-25-035806 / sec_filing / value=15.587B / period=FY2025_Q2

### PLTR

- Verdict: `guard_too_strict`
- Manual-review reason codes: `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`
- Market cap: `349.414B`
- Enterprise value: `341.560B`
- Revenue TTM: `4.701B`
- FCF TTM: `1.627B`
- SBC TTM: `637.921M`
- Shares used: `2.571B`
- Price used: `135.91`
- EV/Sales: `72.65x`
- P/FCF: `214.78x`
- FCF margin: `34.6%`
- SBC/Revenue: `13.6%`
- Fix recommendation: P/FCF is above hard threshold but could be a growth/semiconductor/software context issue; consider sector-aware warning band after validating FCF period.

Evidence IDs / Source IDs:
- `revenue`: PLTR_SEC_COMPANYFACTS_1321655_REVENUE_TTM / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=4.701B / period=None; PLTR_SEC_revenue_FY2025_FY_0001321655-26-000011 / SEC_0001321655_0001321655-26-000011 / sec_filing / value=4.475B / period=FY2025_FY; PLTR_SEC_revenue_FY2025_Q2_0001321655-25-000106 / SEC_0001321655_0001321655-25-000106 / sec_filing / value=1.004B / period=FY2025_Q2; PLTR_SEC_revenue_FY2025_Q3_0001321655-25-000131 / SEC_0001321655_0001321655-25-000131 / sec_filing / value=3.069B / period=FY2025_Q3
- `fcf`: PLTR_SEC_DERIVED_FREE_CASH_FLOW_TTM / SEC_0001321655_DERIVED_FCF / sec_filing / value=3.368B / period=TTM; PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW_TTM / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=1.627B / period=None; PLTR_SEC_COMPANYFACTS_1321655_FCF / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=n/a / period=None; PLTR_SEC_COMPANYFACTS_1321655_FREE_CASH_FLOW / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=n/a / period=None
- `sbc`: PLTR_SEC_DERIVED_SBC_TO_REVENUE / SEC_0001321655_DERIVED_SBC_TO_REVENUE / sec_filing / value=0.17 / period=TTM; PLTR_SEC_COMPANYFACTS_1321655_SBC_TO_REVENUE / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=0.14 / period=None; PLTR_SEC_COMPANYFACTS_1321655_SBC_TTM / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=637.921M / period=None; PLTR_SEC_sbc_FY2025_FY_0001321655-26-000011 / SEC_0001321655_0001321655-26-000011 / sec_filing / value=684.033M / period=FY2025_FY
- `shares`: PLTR_SEC_shares_diluted_FY2025_FY_0001321655-26-000011 / SEC_0001321655_0001321655-26-000011 / sec_filing / value=2.565B / period=FY2025_FY; PLTR_SEC_shares_diluted_FY2025_Q2_0001321655-25-000106 / SEC_0001321655_0001321655-25-000106 / sec_filing / value=2.563B / period=FY2025_Q2; PLTR_SEC_shares_diluted_FY2025_Q3_0001321655-25-000131 / SEC_0001321655_0001321655-25-000131 / sec_filing / value=2.562B / period=FY2025_Q3; PLTR_SEC_shares_diluted_FY2025_Q3_0001321655-25-000131 / SEC_0001321655_0001321655-25-000131 / sec_filing / value=2.571B / period=FY2025_Q3
- `debt`: PLTR_SEC_COMPANYFACTS_1321655_DEBT / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=n/a / period=None; PLTR_SEC_COMPANYFACTS_1321655_TOTAL_DEBT / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=n/a / period=None
- `cash`: PLTR_SEC_COMPANYFACTS_1321655_CASH_AND_EQUIVALENTS / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=2.120B / period=None; PLTR_SEC_COMPANYFACTS_1321655_CASH_AND_INVESTMENTS / PLTR_SEC_COMPANYFACTS_1321655 / sec_filing / value=7.855B / period=None; PLTR_SEC_cash_and_equivalents_FY2025_FY_0001321655-26-000011 / SEC_0001321655_0001321655-26-000011 / sec_filing / value=1.451B / period=FY2025_FY; PLTR_SEC_cash_and_equivalents_FY2026_Q1_0001321655-26-000028 / SEC_0001321655_0001321655-26-000028 / sec_filing / value=1.424B / period=FY2026_Q1
