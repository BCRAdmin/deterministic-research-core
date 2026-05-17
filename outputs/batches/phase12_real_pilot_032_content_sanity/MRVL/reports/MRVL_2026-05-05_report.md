# MRVL Research Report

## Data Basis
- Report as-of date: `2026-05-05`
- Price basis: `168.75 USD` close from `2026-05-05` via `csv_price_provider`
- Source registry: `MRVL_2026-05-05`
- Next earnings date: metric unavailable in validated packet.

## Validated Metric Table

| Metric | Value |
|---|---:|
| Close | 168.75 |
| 50 SMA | 113.34 |
| 200 SMA | 89.36 |
| RSI 14 | 77.12 |
| FCF TTM | 788,700,000 |
| SBC / Revenue | 7.5% |
| EV / Sales | 19.47 |
| P / FCF | 186.08 |

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

- `MRVL_SEC_COMPANYFACTS_1835632` `sec_filing` rank `1` used for `revenue, gross_profit, operating_income, net_income, operating_cash_flow, capex, free_cash_flow, sbc, cash, debt, shares, eps`
- `MRVL_YAHOO_CHART_PRICE_CSV` `exchange_ohlcv` rank `2` used for `price, volume, technical_indicators`