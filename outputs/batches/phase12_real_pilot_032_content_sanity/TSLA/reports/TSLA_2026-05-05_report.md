# TSLA Research Report

## Data Basis
- Report as-of date: `2026-05-05`
- Price basis: `389.37 USD` close from `2026-05-05` via `csv_price_provider`
- Source registry: `TSLA_2026-05-05`
- Next earnings date: metric unavailable in validated packet.

## Validated Metric Table

| Metric | Value |
|---|---:|
| Close | 389.37 |
| 50 SMA | 383.12 |
| 200 SMA | 403.16 |
| RSI 14 | 54.99 |
| FCF TTM | 237,000,000 |
| SBC / Revenue | 2.9% |
| EV / Sales | 14.73 |
| P / FCF | 5,812.62 |

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

- `TSLA_SEC_COMPANYFACTS_1318605` `sec_filing` rank `1` used for `revenue, gross_profit, operating_income, net_income, operating_cash_flow, capex, free_cash_flow, sbc, cash, debt, shares, eps`
- `TSLA_YAHOO_CHART_PRICE_CSV` `exchange_ohlcv` rank `2` used for `price, volume, technical_indicators`