# RFC-0003 — Executable Kernel and Provenance Closure

## Status

Implemented as an additive `compatibility_shadow` layer above immutable
Compiler Foundation 1.0.0 and retained Registry Foundation 1.1.0. BA10 remains
unauthorized.

## Execution authority

The ten BA4–BA9 semantic passes execute only through the frozen Foundation
`PassKernel`. `SemanticCompileStateIR@1` is the linear content-addressed state
carried between passes. The replay entry point loads frozen inputs, invokes
`PassKernel.execute`, and seals the returned execution records. It does not
call semantic pass functions manually.

The seal is deliberately non-circular: L10 evaluates the semantic invariants
inside the kernel. After the kernel returns, the seal binds the ten immutable
`PassExecutionRecord` objects and replaces the provisional kernel diagnostic.
No semantic transformation happens in the seal.

## Provenance closure

- Every embedded legacy formula operand becomes a hash-bound
  `FormulaOperandIR@1` with role, value, dimensions, period and complete
  compatibility-source lineage.
- Formula evaluations bind operand IDs and hashes plus the result Typed Fact.
- The evidence graph contains source input, parsed payload, table, cell,
  normalized record, Typed Fact, metric, formula operand, formula evaluation,
  evidence, source and locator nodes.
- Parsed payloads, tables and cells use content-addressed references after
  their producing pass. Full immutable source bytes and the full table hash
  remain the storage authority; this prevents the same large SEC payload from
  being copied into every subsequent compile-state envelope.
- Table/cell edges are created only for identifiers that actually resolve.
  Unresolved legacy declarations are recorded and never synthesized.

## Decision closure

The RFC-0002 lossless JSON graph remains intact. An additional semantic graph
binds every Registry Foundation 1.1 decision definition for inputs, rules,
risks, counterevidence, score, timing, permissions, non-advice and rationale.
Absent optional legacy categories are explicit `not_present` nodes, not
invented issuer facts.

## Verification closure

L10 binds all L3–L9 artifacts and actual Parsed Payload IR hashes. It adds the
eight RFC-0003 invariants defined by the independent architecture review.
Verdicts remain derived solely from `DiagnosticIR`. Negative fixtures expose a
stable boundary diagnostic code and prove red/green/red plus exact code
identity.

## Compatibility truth

The implementation does not claim source-native fact generation. It does not
change Authority Bundle v3, the frozen canary archives, Product semantic
authority, renderer behavior, release readiness or publication permission.

## Immutable boundary

No file below Compiler Foundation 1.0.0 or Registry Foundation 1.1.0 is
modified. Any future change to these contracts still requires a separate RFC.
