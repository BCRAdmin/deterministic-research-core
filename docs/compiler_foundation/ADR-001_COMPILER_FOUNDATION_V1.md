# ADR-001: Compiler Foundation v1

- Status: accepted and frozen
- Effective date: 2026-08-15
- Foundation version: `1.0.0`
- Scope: BA0, BA1 and BA2
- Decision owner: Room16 operator

## Context

Room16 previously exposed deterministic research capabilities through a large
pipeline and an Authority Bundle, but compiler ownership, pass behavior,
registry authority and cross-language hashing were not one explicit baseline.
BA0–BA2 introduced that baseline as a shadow/strangler extension without
changing legacy output.

## Decision

The twelve layers L0–L11, Research semantic ownership, Product consumer role,
Authority Bundle v3 transition ABI, deterministic Compiler Kernel, Research
Registry Authority and WM/COST/ABT canary freeze form Compiler Foundation v1.

The accepted implementation commits are:

- Research: `e8b75cca33bc8436640872a5ccd7698b43a01e56`
- Product: `089982f039d96065d61537f60591777cd985f14c`
- Tag in both repositories: `room16-compiler-foundation-v1.0.0`

Research alone owns semantic compiler truth. Product owns runtime, queue,
operator UI, renderer execution and release interaction, and consumes only a
hash-verified mirror of Research registries.

## Consequences

- BA0–BA2 are no longer ordinary development surfaces.
- Layer, ownership, registry, pass, IR and ABI changes require an RFC.
- New compiler work is added above the Foundation through versioned contracts.
- Authority Bundle v3 remains stable until an approved migration replaces it.
- WM, COST and ABT validate architecture but cannot define or change it.
- Firm-specific bypasses, registries or compiler branches are prohibited.

## Rejected alternatives

- A rewrite was rejected because it would discard verified deterministic rails.
- Product-owned semantic registries were rejected because they create dual truth.
- Rebaselining canaries during migration was rejected because it hides regressions.
- Company-triggered architecture changes were rejected because they do not generalize.

## Evidence

The binding machine record is
`research_agent/compiler_foundation/freeze/compiler_foundation_manifest_v1.json`.
The accepted Foundation evidence archive has SHA-256
`76502d2ec914b36ee942acd85d14ae07cf984cbf799ac279f2a1e4a1763b2836`.
