# RFC-0001: Semantic Registry Namespace Completion

- Status: `operator_review_required`
- Created: `2026-08-15`
- Scope: Compiler Foundation Registry Authority only
- Requested by: Semantic Compiler Wave BA4–BA9 preflight
- Foundation baseline: `room16-compiler-foundation-v1.0.0`
- Foundation version lock: `8b9b7b2f59aa2cfed8280389f14c0e4edd11846d56c1d78e0dbf2c574da7d518`
- Registry Authority SHA-256: `3cbaea421c51e6a3f1b5dad14fc619fd66d1b5420322b619b76455ac9416a239`
- Implementation authorized: `false`

## Decision requested

Approve a versioned, additive successor to the frozen Registry Authority that
can express generic metric definitions and instances, formula templates,
typed-fact subtypes, claim kinds and decision-graph node/rule kinds required by
BA4–BA9.

The frozen Foundation v1 files, tag, version lock and WM/COST/ABT archives stay
immutable. If approved, the change is released as a new Foundation point
version with a new tag, version lock, Product mirror and conformance evidence.
It must not overwrite or silently reinterpret Foundation v1.

## Why the Semantic Wave stopped

The operator rule says that development must stop, produce an RFC and not
implement a suspected Foundation change. The BA4–BA9 contract preflight found
that the frozen Registry Authority is structurally valid but intentionally too
small to authorize the semantic namespace already present in the accepted
WM/COST/ABT canaries.

The gap is not a company special case:

| Registry | Frozen entries | Accepted canary namespace | Uncovered |
|---|---:|---:|---:|
| Metric | 6 concrete IDs | 282 metric IDs | 276 IDs |
| Formula | 5 primitive operations | 32 formula/template IDs | 32 IDs |
| Claim | 5 abstract kinds | 7 emitted claim kinds | 7 kinds |
| Decision | 3 output concepts | 2 input kinds plus 28 triggered rule IDs | all input/rule kinds |
| Typed fact | 6 broad kinds | 17 legacy fact subtypes, 6 period kinds and 8 dimensions | no authoritative subtype binding |

The detailed, hash-bound audit snapshot is stored beside this RFC in
`RFC-0001_REGISTRY_COVERAGE_AUDIT.json`.

## Root cause

BA2 froze exemplar registries that were sufficient to prove RegistryEnvelope,
hash, Product-mirror and unknown-ID behavior. The entries were not yet a
complete semantic namespace for the accepted research system.

That distinction was not blocking for BA0–BA3 because Source Front-End uses the
source registry and the existing provider-capability binding. It becomes
blocking at BA5–BA9:

1. BA5 cannot claim that every fact type is registry-authorized while subtype
   mappings live only in Python.
2. BA6 cannot emit a registered FormulaEvaluationIR for formulas such as
   `cfo_minus_capex`, `annual_minus_prior_interim_plus_current_interim` or
   `equity_dcf_sensitivity_v1`.
3. BA6 cannot bind period-, segment- and issuer-specific metric instances to a
   generic registered metric definition without an authoritative instance
   grammar.
4. BA8 cannot map `rating`, `risk`, `news`, `guidance`, `financial_metric`,
   `technical_metric` and `valuation_metric` without inventing lossy aliases.
5. BA9 cannot represent risk inputs, operating signals, permission corridors,
   counterpositions and rule lineage with only `rating`, `scenario` and
   `confidence`.

## Rejected workarounds

### Add 276 canary metric IDs directly

Rejected. Many IDs contain periods, segments or occurrence suffixes and are
metric instances, not reusable definitions. Registering them would encode the
three canaries into architecture and violate the no-company-patch rule.

### Map every unknown ID to the nearest existing entry

Rejected. Mapping a rating claim to `outlook`, a risk claim to `causal`, or a
DCF formula to `sum` would make validation green by changing meaning.

### Create a wave-local second registry

Rejected. This would violate the frozen Research/Product truth boundary and
the rule that Research owns one Registry Authority.

### Continue BA4–BA5 and stop later

Rejected for this milestone. BA4–BA9 were authorized as one Semantic Compiler
Wave. Building partial contracts around a known authority gap would create a
new intermediate architecture that cannot honestly complete the wave.

## Proposed minimal change

### 1. Preserve Foundation v1 immutably

- Keep tag `room16-compiler-foundation-v1.0.0` unchanged in both repositories.
- Keep the v1 Registry Authority document and its SHA-256 unchanged.
- Keep Authority Bundle v3, layers L0–L11, ownership, Compiler Kernel, Shadow
  Migration and WM/COST/ABT candidate hashes unchanged.

### 2. Add a versioned Registry Authority successor

- Add a v2 authority document rather than editing the v1 document in place.
- Teach the Research loader to select an explicitly version-locked authority;
  no `latest` lookup and no silent fallback.
- Mirror only the selected, hash-bound authority into Product.
- Emit a new Foundation point-version freeze record and Git tags after all
  conformance and canary tests pass.

### 3. Separate definitions from deterministic instances

- Registry entries remain generic semantic definitions.
- A new Semantic-Wave `MetricInstanceBindingIR@1` binds a concrete metric
  instance to exactly one registered definition, parameters, period, segment,
  occurrence, unit and stable instance hash.
- The Registry Authority owns the allowed namespaces and parameter grammar.
- Unknown namespaces, ambiguous pattern matches and unbound parameters fail
  closed.

### 4. Complete only generic registry families

The successor authority should add reusable families, not company IDs:

- metrics: core financial, market, technical, valuation, risk, guidance,
  filing numeric, operating KPI, capital allocation and scenario metrics;
- formulas: the currently used generic formula templates plus an explicit
  composition/expression contract for primitive operations;
- typed facts: comparison, stock, run-rate, reconciliation, contribution,
  policy, basis-point and per-share subtypes with deterministic mapping to the
  existing broad kinds;
- claims: the seven currently emitted domain kinds with explicit mapping to
  numeric/comparison/trend/causal/outlook semantics;
- decisions: risk input, operating signal, score input, rating permission,
  counterposition, scenario, confidence, non-advice boundary and generic rule
  template kinds.

### 5. Do not change passes or layer ownership

This RFC does not authorize changes to:

- L0–L11;
- Compiler Kernel protocol;
- existing Foundation pass order;
- Authority Bundle v3 ABI;
- Research/Product ownership;
- current canary baselines;
- BA10 or renderer behavior.

## Compatibility policy

- Foundation v1 remains readable and replayable forever.
- A v1 compile request cannot silently consume v2 registries.
- A v2 compile request must bind the new authority SHA-256 and point-version
  lock explicitly.
- Additive registry entries are not enough on their own: all instance grammar,
  alias mappings and formula templates are part of the hash-bound authority.
- Unknown fields and unknown IDs remain fail-closed.

## Required implementation order after approval

1. Freeze RFC acceptance and exact allowed delta.
2. Add v2 authority document and version-selecting loader without changing v1.
3. Add generic definition/instance binding contracts.
4. Add Product read-only mirror and exact lock.
5. Run positive, negative, tamper, version, unknown-ID, pattern-collision and
   cross-language conformance tests.
6. Replay WM, COST and ABT twice from the accepted archives.
7. Verify all existing candidate ZIP SHA-256 values remain unchanged.
8. Issue the new point-version freeze record and tags.
9. Resume BA4–BA9 from the approved authority hash.

## Required tests

- frozen v1 tag, files, hashes and version lock remain byte-identical;
- v1 and v2 readers reject the wrong authority version;
- every generic registry entry resolves in Python and Product JavaScript;
- every accepted canary metric instance resolves to exactly one definition;
- an unknown or multiply matching metric instance fails closed;
- all 32 current formula IDs resolve to registered templates or an explicitly
  registered expression composition;
- all seven current claim kinds bind without lossy aliasing;
- decision inputs and triggered rules bind to generic registered definitions;
- mirror tamper, authority tamper and lock tamper fail closed;
- WM/COST/ABT shadow replay is deterministic across two runs;
- WM/COST/ABT accepted candidate archive hashes remain exactly unchanged;
- Authority Bundle v3 output remains unchanged.

## Risks

- A loose metric-instance grammar could accept misspellings as valid metrics.
- Pattern overlap could create ambiguous authority.
- Formula templates could become a hidden second calculation engine unless
  operands and expression semantics are explicit.
- An in-place registry edit would invalidate the Foundation v1 freeze.
- Product could accidentally select v2 without the matching Research lock.

All five risks are release blockers for the RFC implementation.

## Definition of Done for this RFC

This RFC is complete only when:

- the operator explicitly approves or rejects it;
- an approval identifies the exact Foundation point version;
- implementation evidence proves v1 immutability and v2 fail-closed behavior;
- Product contains no writable or independently interpreted registry truth;
- WM/COST/ABT hashes are unchanged;
- BA4–BA9 resumes only after the new freeze record is accepted.

## Current verdict

```json
{
  "foundation_changed": false,
  "semantic_wave_implementation_started": false,
  "ba4_started": false,
  "ba10_started": false,
  "rfc_required": true,
  "rfc_status": "operator_review_required",
  "reason": "frozen_registry_authority_cannot_authorize_current_semantic_namespace_without_loss_or_parallel_truth"
}
```
