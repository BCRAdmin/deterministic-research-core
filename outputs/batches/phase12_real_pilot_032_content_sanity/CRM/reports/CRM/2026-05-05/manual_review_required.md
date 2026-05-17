# CRM Research Report

## Data Basis
- Report as-of date: `2026-05-05`
- Price basis: `186.99 USD` close from `2026-05-05` via `csv_price_provider`
- Source registry: `CRM_2026-05-05`
- Next earnings date: metric unavailable in validated packet.

## Validated Metric Table

| Metric | Value |
|---|---:|
| Close | 186.99 |
| 50 SMA | 186.82 |
| 200 SMA | 227.83 |
| RSI 14 | 53.99 |
| FCF TTM | 10,858,000,000 |
| SBC / Revenue | 8.2% |
| EV / Sales | 4.23 |
| P / FCF | 16.46 |

## Validation Status

- `warning` `EARNINGS_DATE_UNAVAILABLE`: Next earnings date is unavailable; report must state that it is unconfirmed.

## Analyst Interpretation

No LLM claims attached. Use validated packets before adding interpretation.

## Rating Permission

- Preferred rating: `Hold`
- Allowed ratings: `Hold, Accumulate, Tactical Trim`
- Blocked ratings: `Strong Buy, Buy, Tactical Underweight, Underweight, Sell, Avoid`
- Reason: Mixed signals require a neutral-to-tactical rating corridor.

## Source Quality

- `CRM_SEC_COMPANYFACTS_1108524` `sec_filing` rank `1` used for `revenue, gross_profit, operating_income, net_income, operating_cash_flow, capex, free_cash_flow, sbc, cash, debt, shares, eps`
- `CRM_YAHOO_CHART_PRICE_CSV` `exchange_ohlcv` rank `2` used for `price, volume, technical_indicators`