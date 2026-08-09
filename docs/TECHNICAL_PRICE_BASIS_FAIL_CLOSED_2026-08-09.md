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
`b702fa2c6ee2f557e5e576f08572c0fa6ba26ef1c5a5bebb16d9337ec7bb8f13` and
passes the full Authority contract.

Its current decision output is:

- `technical_status=partial`;
- `technical_score=0.0`;
- no `TREND_STATE_BULLISH` or `TREND_STATE_BEARISH` rule;
- no numeric `risk_markers`; and
- an explicit technical boundary explaining that corporate-action adjustment
  is not confirmed.

No Tiingo, Massive, Polygon or other paid data source was configured or
queried.

## Verification

- Complete research test suite: `718 passed`.
- Ruff: all research files pass.
- Product Authority dry-run copied the bundle before interpretation and
  matched recorded and copied manifest hashes exactly.

This is a generic system rule. It is not a KO-specific exception.
