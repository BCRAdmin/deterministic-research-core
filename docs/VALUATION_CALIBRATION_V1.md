# Room16 Valuation Calibration v1

> Data-provider gate: the preferred but still disabled candidate, rights
> questions, and staged cost architecture are documented in
> [`VALUATION_DATA_PROVIDER_DECISION_2026-08-09.md`](VALUATION_DATA_PROVIDER_DECISION_2026-08-09.md).
> An adapter or API token is not a live-use approval.

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

## Retrospective point-in-time replay

Room16 does not need to wait a full year before beginning methodology tests,
but a report rebuilt today for an old date is not automatically historical
evidence. A retrospective candidate qualifies only through
`room16.valuation_calibration_replay@1`:

- the raw SEC CompanyFacts file, raw OHLCV file and issuer identity are copied
  into an isolated replay root and hash-bound;
- every CompanyFacts row filed after the historical cutoff is removed, and an
  undated row is never admitted;
- every price observation after the cutoff is removed;
- the sanitized inputs, exact Authority Manifest, Fact Ledger and base
  valuation snapshot are bound into the replay manifest;
- the complete pipeline must come from a clean, committed Git worktree;
- the replay is permanently marked `publication_allowed: false`; and
- a promoted replay snapshot receives a distinct ID bound to the replay
  manifest. It can enter calibration evidence but never the report library.

Two pipeline versions of the same issuer, report date and price-basis date are
one economic observation, not two samples. Readiness rejects all such
duplicates until the superseded replay is removed from the evaluated corpus.
This prevents repeated reruns from manufacturing sample size.

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
only `room16.valuation_calibration_source_bundle@2` files and rebuilds every
outcome deterministically. Each source bundle binds:

- the exact snapshot, instrument, benchmark and basis date;
- provider and dataset identity;
- separate total-return assurances for instrument and benchmark, each covering
  cash distributions and corporate actions;
- local relative paths and hashes for provider methodology, instrument data,
  benchmark data, usage-rights evidence and human-verification evidence;
- a timezone-aware bundle-creation timestamp; retrieval, rights approval and
  verification may not be dated after the package that claims to contain them;
- an explicit `internal_calibration_allowed` decision with a human rights
  approver and timezone-aware decision timestamp;
- identified data preparation plus a different, non-automation human reviewer,
  a timezone-aware verification timestamp, an explicit independence assertion
  and a separate verification-evidence artifact; and
- the complete normalized price series under one bundle hash.

A changed observation, conflicting duplicate date, missing distribution or
corporate-action assurance, unverified methodology, missing/tampered artifact,
path traversal, nonhuman approval identity, self-review or stale bundle hash
invalidates the outcome before it can enter readiness. Version-1 source bundles
are deliberately rejected because they did not make the evidence artifacts,
rights approver and review independence machine-verifiable. This contract is
provider-neutral: a public source may qualify if it proves the same semantics;
an expensive vendor does not qualify merely because it is paid.

## Outcome workbench

The workbench has two modes, but only one outcome methodology:

- `draft` copies the supplied price files into a self-contained review packet,
  calculates a preview and lists every missing semantic, rights or review gate.
  It never claims that the source contract is valid.
- `verified` refuses ineligible snapshots, raw or merely split-adjusted prices,
  incomplete distribution/corporate-action assurances, absent evidence,
  automation identities, self-review, naive timestamps and observations after
  retrieval. It writes no partial output on failure.

Draft example:

```bash
python -m research_agent.calibration.valuation_outcome_workbench \
  --mode draft \
  --snapshot <VALUATION_SNAPSHOT_JSON> \
  --instrument-series <NORMALIZED_INSTRUMENT_DATE_CLOSE_CSV> \
  --benchmark-series <NORMALIZED_BENCHMARK_DATE_CLOSE_CSV> \
  --provider-id <CANDIDATE_PROVIDER> \
  --provider-dataset-id <CANDIDATE_DATASET> \
  --benchmark <BENCHMARK_ID> \
  --retrieved-at <TIMEZONE_AWARE_TIMESTAMP> \
  --instrument-series-basis <KNOWN_OR_UNVERIFIED_BASIS> \
  --benchmark-series-basis <KNOWN_OR_UNVERIFIED_BASIS> \
  --prepared-by <PREPARER_IDENTITY> \
  --output-dir <NEW_EMPTY_OUTPUT_DIR>
```

Verified mode uses the same command with `--mode verified`, both bases set to
`total_return_adjusted`, all four distribution/corporate-action confirmation
flags and these evidence/review arguments:

```text
--provider-methodology-evidence <FILE>
--usage-rights-evidence <FILE>
--verification-evidence <SEPARATE_FILE>
--prepared-by <IDENTITY>
--rights-approved-by <HUMAN_IDENTITY>
--rights-approved-at <TIMEZONE_AWARE_TIMESTAMP>
--verified-by <DIFFERENT_HUMAN_IDENTITY>
--verified-at <TIMEZONE_AWARE_TIMESTAMP>
--approve-internal-calibration-rights
--confirm-independent-review
```

The generated packet remains calibration evidence only. Even a valid matured
outcome keeps `live_activation_allowed: false`; publication and paid-product
rights are not inferred from the narrower internal-calibration approval.

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
  --retrospective-replay-root <OPTIONAL_VERIFIED_REPLAY_ROOT> \
  --outcome-source-root <OPTIONAL_VERIFIED_SOURCE_BUNDLES> \
  --output-dir <RUNTIME_OUTPUT_DIR>
```

A replay itself is built from already acquired raw inputs:

```bash
python -m research_agent.calibration.retrospective_replay \
  --ticker <TICKER> \
  --date <HISTORICAL_CUTOFF> \
  --raw-companyfacts <RAW_SEC_COMPANYFACTS_JSON> \
  --raw-prices <RAW_OHLCV_CSV> \
  --cik-records <ISSUER_IDENTITY_JSON> \
  --replay-root <RUNTIME_REPLAY_ROOT>
```

The command deliberately refuses a dirty worktree and refuses to overwrite an
existing replay with the same input and pipeline identity.

Optional sector identities may be supplied as a ticker-to-sector JSON object.
Until verified source bundles contain real matured observations, the correct
result is `not_ready` and valuation remains neutral in the decision engine.
