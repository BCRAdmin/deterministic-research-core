# Compiler Foundation Changelog

## 2026-08-15 — Registry Foundation 1.1.0 frozen

- RFC-0001 als additive Registry Foundation 1.1.0 umgesetzt.
- Definition und Instanz für Metric, Formula, Claim und Decision getrennt.
- 100 Prozent der WM-/COST-/ABT-Identifier klassifiziert; Unknowns und
  semantische Kollisionen blockieren fail closed.
- DCF-Policy-Parameter von DCF-Evaluation und Prozentquoten von Multiplikatoren
  semantisch getrennt.
- Research Authority und Product Read-only-Mirror mit gemeinsamen Hashes
  eingefroren.
- Neun BA4–BA9-Pass-Contracts gebunden; BA10 bleibt unautorisiert.

## 1.0.0 - 2026-08-15

Status: accepted and frozen.

### Added

- canonical L0–L11 layer and ownership constitution;
- versioned IR, registry, diagnostic, verdict, provenance, quarantine and
  compatibility envelopes;
- deterministic pass protocol with content-addressed cache and hash-verified replay;
- Research-owned Registry Authority and hash-verified Product mirror;
- shadow replay chain for legacy runs;
- cross-language canonical JSON conformance;
- WM/COST/ABT frozen-canary verification;
- machine-verifiable Foundation manifest and version lock.

### Compatibility

- Authority Bundle v3 unchanged;
- existing reports and canary archives unchanged;
- Product semantic behavior unchanged;
- BA3 not part of version 1.0.0.

### Governance

Any future Foundation change requires an approved RFC and a new version. BA3+
feature work does not alter this changelog unless it changes the Foundation
through that process.
