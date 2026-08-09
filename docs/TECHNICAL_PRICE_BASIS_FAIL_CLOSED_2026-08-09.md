# Room16: Fail-closed technical scoring by price-series basis

Date: 2026-08-09

## Trigger

A fresh, no-cost KO run for 2026-08-07 used SEC and issuer filings for
fundamentals and Nasdaq's public OHLCV surface for prices. The resulting price
series correctly declared `unadjusted_or_provider_default`, but the decision
packet still emitted:

- technical score `1.0`;
- triggered rule `TREND_STATE_BULLISH`; and
- numeric SMA-based `review_level` and `downside_reference` markers.

The technical score was excluded from the long-term composite, but the exposed
direction and levels could still be over-interpreted by a report model or a
reader. The behavior therefore remained unsafe even though the final rating
was capped at `Hold`.

A second output-path audit then found the same unsafe direction in deterministic
claim and report composition even after the score and action policy had been
fixed. The binding rule now applies to executive summaries, technical sections,
bull and bear cases, catalyst/reference language, scenario text, rating
explanations and both rendered report variants.

## Binding rule

- `corporate_action_adjusted`: technical direction may be scored and numeric
  policy levels may be exposed.
- `post_corporate_action_only`: technical direction may be scored as limited,
  post-action timing evidence; the report must retain the longer-horizon
  limitation.
- every other basis, including `unadjusted_or_provider_default` and `unknown`:
  indicators may remain as provisional observations, but the technical score
  is `0`, no directional decision rule is triggered, and numeric policy levels
  are withheld.

A zero financial-risk contribution is now labelled explicitly as a downside
contribution and never as a low-risk conclusion.

## Verified KO replay

The rebuilt KO 2026-08-07 Authority Bundle has manifest SHA-256
`815fe9697d701c3c5b4ea9f51dcfe97916b4ec8a11bda925fafa00894121c22f` and
passes the full Authority contract.

Its current decision output is:

- `technical_status=partial`;
- `technical_score=0.0`;
- no `TREND_STATE_BULLISH` or `TREND_STATE_BEARISH` rule;
- no numeric `risk_markers`; and
- an explicit technical boundary explaining that corporate-action adjustment
  is not confirmed.

The report surfaces now state that raw indicators cannot inform timing and do
not expose moving averages as support, resistance, risk or trigger levels.

## Independent financial-period audit

The same KO replay was independently recomputed from the staged SEC
CompanyFacts rows:

- revenue TTM: `47.941B - 23.664B + 25.852B = 50.129B`;
- operating cash flow TTM: `7.408B - (-1.391B) + 7.543B = 16.342B`;
- capex TTM: `2.112B - 0.751B + 0.684B = 2.045B`;
- FCF TTM: `16.342B - 2.045B = 14.297B`;
- dividends TTM: `8.779B - 2.283B + 4.562B = 11.058B`;
- buybacks TTM: `0.746B - 0.472B + 0.663B = 0.937B`; and
- shareholder distributions: `11.058B + 0.937B = 11.995B`.

This audit exposed a separate period-binding defect: the YTD cash-flow claim
correctly displayed `684M` of YTD capex but its Fact Ledger selected the same
date's `418M` quarterly row. Current-period claims can now provide their exact
period values to evidence selection. The rebuilt claim and Fact Ledger both
bind operating cash flow and capex to `2026-01-01..2026-07-03`, with YTD values
`7.543B` and `684M` respectively.

Compact SEC accessions in deterministic lineage are now also resolved to the
registered canonical SEC source IDs. TTM facts therefore retain their complete
primary-source chain instead of showing only the calculation source.

The share-count basis was reviewed but intentionally not changed. Market cap
continues to use the verified listed-class share count, while the slightly newer
cover-page economic-share observation remains separate. Applying an aggregate
economic count to one listed-class price without class-equivalence evidence
would be less conservative.

No Tiingo, Massive, Polygon or other paid data source was configured or
queried.

## Verification

- Complete research test suite: `723 passed`.
- Ruff: all research files pass.
- Product Authority dry-run copied the bundle before interpretation and
  matched recorded and copied manifest hashes exactly.

This is a generic system rule. It is not a KO-specific exception.
