# NFLX Research Report

## Data Basis
- Report as-of date: `2026-05-05`
- Price basis: `87.89 USD` close from `2026-05-05` via `csv_price_provider`
- Source registry: `NFLX_2026-05-05`
- Next earnings date: metric unavailable in validated packet.

## Validated Metric Table

| Metric | Value |
|---|---:|
| Close | 87.89 |
| 50 SMA | 95.16 |
| 200 SMA | 103.82 |
| RSI 14 | 34.15 |
| FCF TTM | 12,682,821,000 |
| SBC / Revenue | 0.8% |
| EV / Sales | 8.14 |
| P / FCF | 29.79 |

## Validation Status

- `warning` `EARNINGS_DATE_UNAVAILABLE`: Next earnings date is unavailable; report must state that it is unconfirmed.

## Analyst Interpretation

No LLM claims attached. Use validated packets before adding interpretation.

## Rating Permission

- Preferred rating: `Hold`
- Allowed ratings: `Hold, Tactical Trim, Tactical Underweight`
- Blocked ratings: `Strong Buy, Buy, Accumulate, Underweight, Sell, Avoid`
- Reason: Business quality is positive, but technical trend is weak and risk controls matter.

## Source Quality

- `NFLX_SEC_COMPANYFACTS_1065280` `sec_filing` rank `1` used for `revenue, gross_profit, operating_income, net_income, operating_cash_flow, capex, free_cash_flow, sbc, cash, debt, shares, eps`
- `NFLX_YAHOO_CHART_PRICE_CSV` `exchange_ohlcv` rank `2` used for `price, volume, technical_indicators`