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
- the input price series is explicitly corporate-action adjusted.

An unadjusted Nasdaq series, an illustrative multi-class value or an
incomplete scenario is excluded. A green report audit cannot waive these
requirements.

## Outcome contract

Valuation is tested at a minimum 252-trading-day horizon. Each outcome must:

- refer to exactly one snapshot ID;
- use future observations only;
- carry a source hash;
- use corporate-action-adjusted instrument and benchmark series; and
- contain exactly 252 common future trading observations, calculated by the
  deterministic outcome builder rather than asserted by report prose; and
- reconcile instrument return minus benchmark return exactly to excess
  return.

Missing, duplicate, immature, unadjusted or arithmetically inconsistent
outcomes do not enter the sample.

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
  --output-dir <RUNTIME_OUTPUT_DIR>
```

Optional hashed 252D outcomes may be supplied as JSONL and sector identities
as a ticker-to-sector JSON object. Until those real observations mature, the
correct result is `not_ready` and valuation remains neutral in the decision
engine.
