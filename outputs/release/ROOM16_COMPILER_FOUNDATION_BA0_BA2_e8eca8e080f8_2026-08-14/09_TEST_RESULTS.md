
# Test Results

| Prüfung | Ergebnis |
|---|---|
| /Users/BjornRosinger/Documents/DreamFactory/Room16/research-agent-ops/.venv/bin/python -m pytest -q | PASS |
| /Users/BjornRosinger/Documents/DreamFactory/Room16/company-dossier-lab/.venv/bin/python -m pytest -q | PASS |
| npm run verify:compiler-foundation | PASS |
| npm run lint | PASS |
| npm run verify | PASS |
| /Users/BjornRosinger/Documents/DreamFactory/Room16/research-agent-ops/.venv/bin/ruff check research_agent/compiler_foundation research_agent/tests/test_compiler_foundation_contracts.py research_agent/tests/test_compiler_foundation_pass_protocol.py research_agent/tests/test_compiler_foundation_registry.py research_agent/tests/test_compiler_foundation_shadow.py | PASS |

Erfasster Umfang: 1.098 Research-Python-Tests, 536 Product-Python-Tests plus 41 Subtests,
33 bestehende Product-JavaScript-Tests, 121 neue Foundation-Python-Tests und 7 neue
Cross-Language-/Mirror-JavaScript-Tests. Die erste Product-Verifikation ohne Cycle-Ausnahme
meldete ausschließlich einen älter als 30 Minuten gewordenen Hardening-Zeitstempel; die
Regression wurde anschließend mit dem dafür vorgesehenen
`ROOM16_VERIFY_SKIP_HARDENING_STATE=1`-Cycle-Modus vollständig grün ausgeführt.

Die Matrix enthält für jeden Pass und jede Registry positive, negative, Tamper-,
Versionierungs-, Unknown-ID/Dependency-, Reihenfolge-, Skip-, Replay- und
Cross-Language-Prüfungen. Nicht-skippable Pässe bestehen den Skip-Test, indem sie den
Skip-Versuch fail-closed ablehnen.

## Pass-Matrix

| Pass | Positive | Negative | Tamper | Version | Unknown-ID | Order | Skip | Replay | Cross-language |
|---|---|---|---|---|---|---|---|---|---|
| `foundation.l0_compile_intake_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l1_source_acquisition_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l2_source_snapshot_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l3_parse_discover_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l4_normalize_reconcile_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l5_typed_fact_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l6_metric_formula_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l7_evidence_graph_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l8_claim_graph_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l9_decision_graph_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l10_verification_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `foundation.l11_emit_observe` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

## Registry-Matrix

| Registry | Positive | Negative | Tamper | Version | Unknown-ID | Order | Skip/Removal | Replay | Cross-language |
|---|---|---|---|---|---|---|---|---|---|
| `room16.registry.claim` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `room16.registry.decision` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `room16.registry.diagnostic` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `room16.registry.evidence_policy` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `room16.registry.formula` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `room16.registry.metric` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `room16.registry.source` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `room16.registry.table` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `room16.registry.typed_fact` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `room16.registry.verdict` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
