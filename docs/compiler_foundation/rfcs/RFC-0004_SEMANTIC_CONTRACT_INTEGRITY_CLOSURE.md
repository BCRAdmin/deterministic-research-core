# RFC-0004 — Semantic Contract Integrity Closure

Status: IMPLEMENTED, AWAITING INDEPENDENT REVIEW

Scope: RFC3-AR-001 through RFC3-AR-005 only

BA10: NOT AUTHORIZED

## Decision

RFC-0004 closes the five remaining semantic-integrity findings above the
frozen Foundation 1.0.0 and retained Registry Foundation 1.1.0. The accepted
Foundation PassKernel remains the only pass execution authority. No Product
semantic authority, company-specific rule, renderer cutover, report rebuild or
Authority Bundle v4 is introduced.

## RFC3-AR-001 — Registry-aware cache and replay lock

`SemanticCompileStateIR@2` binds a content-addressed
`SemanticRegistryLockIR@1` before the first kernel pass. The lock contains the
Semantic Registry Authority hash, Metric Signature Authority hash, formula,
evidence, claim and decision policy hashes, pass-manifest hash, compiler
implementation commit, version and implementation-source hash. Because the
lock is part of the initial state payload, it affects the first input payload
hash and every downstream cache key.

The required mutation fixture proves:

`same source + changed signature authority => executed, never cache_hit`.

## RFC3-AR-002 — Formula operand semantics

Every formula role is checked against its exact Formula Registry legacy role
contract and resolves to one of:

1. an existing typed fact with its own evidence;
2. an evidence-backed `FormulaOperandFactIR` with an operand-specific evidence
   locator;
3. a registered `PolicyParameterIR` from the hash-bound RFC-0004 policy set;
4. `quarantined_unresolved_operand`, which blocks L10.

Result-fact dimension, unit, period and evidence are no longer copied into
operands. L10 checks role existence and pattern, cardinality, required roles,
dimension, target identity, value equality, evidence binding and result
dimension.

## RFC3-AR-003 — Canonical table/cell lineage

Every discovered `SemanticTableIR` receives a content-addressed
`room16-table://sha256/<ir-hash>` reference with cell count and locator
contract. A deterministic compatibility mapper uses source snapshot path,
source value/value-state, row and column semantics, segment and period axes to
map legacy table/cell IDs to canonical IDs. It contains no ticker, issuer or
legacy table-ID lookup table.

Complete tables can be reproduced from the frozen archive through
`iter_canonical_table_artifacts`. The Evidence Bundle materializes the
content-addressed table store and verifies every reference. Unresolved
executable fact lineage blocks the three new L10 gates.

## RFC3-AR-004 — Decision lineage

`SemanticDecisionNodeIR@2` separates present instances from optional
`not_present_schema_coverage` nodes. Present decision inputs, risks, rules,
scores and rationales bind real claim, fact, evidence and source IDs. Scores
also bind a registered score definition; permissions bind policy definitions.
Not-present nodes cannot contribute to instance-lineage completeness.

L10 independently checks claim lineage, fact/evidence lineage, score inputs
and risk/counterevidence bindings.

## RFC3-AR-005 — Execution attestation boundary

The L10 report contains semantic diagnostics only and is sealed by L10.
`PASS_KERNEL_EXECUTION_COMPLETE` and `FIXTURE_DIAGNOSTIC_CODES_STABLE` are no
longer issuer diagnostics. `ExecutionAttestationIR@1` is created after the
kernel and binds the final compile state, sealed Verification Report, all pass
execution record hashes and the build-level fixture attestation. It is not a
semantic pass and does not pre-empt BA10.

## Immutable boundaries

- Compiler Foundation 1.0.0: unchanged
- Registry Foundation 1.1.0: unchanged
- Authority Bundle v3: unchanged
- WM/COST/ABT Canary archives: byte-identical
- Product semantic authority: absent
- compiler mode: `compatibility_shadow`
- source-native fact generation: `false`
- release/publication/renderer cutover: `false`
- BA10: `false`, not started

## Definition of Done

RFC-0004 is implementation-complete only when all three frozen canaries pass
the strengthened L10 gates, the negative fixtures emit the exact promised
diagnostic codes, registry mutation prevents cache hits, the canonical table
store resolves and hash-verifies, executed/cache-hit/replay converge, Research
and Product full regressions pass, all freeze verifiers pass, the Evidence ZIP
rebuilds byte-identically and the next review is limited to RFC3-AR-001 through
RFC3-AR-005.
