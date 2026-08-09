# Room16 Valuation Calibration v1

## Purpose

The standardized DCF in Analytical Core v0.2 is sensitivity evidence, not a
validated fair-value model. Valuation Calibration v1 creates the missing
point-in-time dataset contract without activating a rating signal.

## Eligible snapshot

A snapshot enters the calibration candidate set only when:

- the exact `metrics_packet.json` and Authority Manifest are hash-bound;
- DCF status and reverse DCF are measured;
- bear, base and bull upside values are complete;
- the share-count basis is verified; and
- the point-in-time close is dated, positive and no later than the report.

The historical technical-series adjustment does not gate a DCF snapshot: DCF
uses the point-in-time equity value, not past technical returns. An
illustrative multi-class value or an incomplete scenario remains excluded. A
green report audit cannot waive these requirements.

Every completed research run stores the immutable snapshot next to its
Authority Bundle. Its ID binds the exact metrics and Authority Manifest
hashes. Sector classification is a separately hash-bound calibration overlay
and therefore does not rewrite the valuation snapshot ID.

## Outcome contract

Valuation is tested at a minimum 252-trading-day horizon. Each outcome must:

- refer to exactly one snapshot ID;
- use future observations only;
- carry a source hash;
- use total-return-adjusted instrument and benchmark series from the same
  basis date, including cash distributions rather than merely split-adjusted
  closes;
- contain exactly 252 common future trading observations, calculated by the
  deterministic outcome builder rather than asserted by report prose; and
- reconcile instrument return minus benchmark return exactly to excess
  return.

Missing, duplicate, immature, unadjusted or arithmetically inconsistent
outcomes do not enter the sample.

Outcome values are never accepted as free-form JSONL. The active runner loads
only `room16.valuation_calibration_source_bundle@1` files and rebuilds every
outcome deterministically. Each source bundle binds:

- the exact snapshot, instrument, benchmark and basis date;
- provider and dataset identity;
- separate total-return assurances for instrument and benchmark, each covering
  cash distributions and corporate actions;
- hashes of provider methodology, instrument data and benchmark data plus an
  explicit `internal_calibration_allowed` usage-rights decision bound to its
  evidence;
- an independent human-verification record with reviewer, timestamp and
  evidence hash; and
- the complete normalized price series under one bundle hash.

A changed observation, conflicting duplicate date, missing distribution or
corporate-action assurance, unverified methodology or stale bundle hash
invalidates the outcome before it can enter readiness. This contract is
provider-neutral: a public source may qualify if it proves the same semantics;
an expensive vendor does not qualify merely because it is paid.

## Readiness policy

The initial conservative governance floor is:

- 75 effective matured observations;
- at least 25 unique issuers;
- at least five sectors; and
- at most three effective observations per issuer.

These are admission gates, not proof of predictive value. Reaching them only
creates `shadow_ready`. Room16 still requires an independent methodology
review, stability tests and an explicit signed operator promotion before a
calibrated valuation score could become live. The readiness runner never
changes ratings automatically.

## Runner

```bash
python -m research_agent.calibration.valuation_calibration \
  --authority-root <ROOT_WITH_TICKER_DATE_BUNDLES> \
  --outcome-source-root <OPTIONAL_VERIFIED_SOURCE_BUNDLES> \
  --output-dir <RUNTIME_OUTPUT_DIR>
```

Optional sector identities may be supplied as a ticker-to-sector JSON object.
Until verified source bundles contain real matured observations, the correct
result is `not_ready` and valuation remains neutral in the decision engine.
