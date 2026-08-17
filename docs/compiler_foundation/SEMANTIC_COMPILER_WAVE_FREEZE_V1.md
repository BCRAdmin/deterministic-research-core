# Room16 Semantic Compiler Wave v1 Freeze

Status: **ACCEPTED / FROZEN** seit 2026-08-17.

Die Semantic Compiler Wave `1.0.0` friert BA3 bis BA9 nach der unabhängigen
Akzeptanz von RFC-0004 ein. BA0 bis BA2 bleiben unverändert als Compiler
Foundation `1.0.0` und Registry Foundation `1.1.0` bestehen. Authority Bundle
v3 bleibt Übergangs-ABI; WM, COST und ABT bleiben unveränderte Canaries.

## Freeze-Koordinaten

| Bestandteil | Eingefrorener Wert |
|---|---|
| Semantic-Wave-Version | `1.0.0` |
| Git-Tag | `room16-semantic-compiler-wave-v1.0.0` |
| Research-Commit | `b498c5c2835682b3f81dc475a276df6ab58a79fd` |
| Product-Commit | `82c5525f3291ace4e3d8c0fdeee6bd67348f5a38` |
| Foundation-Version | `1.0.0` |
| Registry-Version | `1.1.0` |
| Pass-Manifest-Hash | `854abab7764f1a26a26ac2a97585171154aaac52c2eb8ecb848e800d2da02d33` |
| IR-Schema-Hash | `b7b6194ad05b023c1c1cb1fe2a5cba6d5f830dfd6ee400df954c35c997847f4c` |
| Semantic-Source-Set-Hash | `a4cf0a112b47fb603b04fa2ff1a816f826b338661290edf91ae6bd05c0623dae` |
| Canary-Baseline-Hash | `88795b625b2d9ab892b559d98b6d4d0a0c79364088fe7376dc49a3b8bd796d7f` |
| Semantic-Evidence-Hash | `70603e61dc0d1b8b5e982688f966a0b5d0196311b1185a82f0e5d69ad4ea0875` |
| Semantic-Version-Lock | `62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9` |

Der maschinenlesbare Freeze Record liegt unter
`research_agent/semantic_compiler/freeze/semantic_compiler_wave_freeze_v1.json`.

## Eingefrorene Pass-Kette

Die zehn effektiven Semantic-Pässe reichen von `ba4.l3.parse_sources` über
Parse, Table Discovery, Normalize, Facts, Metrics, Formulas, Evidence, Claims
und Decisions bis `ba9.l10.verify_semantics`. Der Hash bezieht sich auf die
vom unveränderten Foundation-PassKernel tatsächlich geladenen
`PassManifest`-Objekte, nicht nur auf die Rohdatei.

Der IR-Schema-Hash bindet `91` Pydantic-Schemata aus Foundation, Source
Front-End, Registry Foundation, Semantic Wave, Semantic Spine sowie den
RFC-0003- und RFC-0004-Contracts.

## RFC-Historie

- RFC-0001: Registry Foundation `1.1.0` akzeptiert und eingefroren.
- RFC-0002: Richtung erhalten; offene Architekturfindings führten zu RFC-0003.
- RFC-0003: Ausführungskern und Provenienz akzeptiert; fünf offene Findings
  führten zu RFC-0004.
- RFC-0004: vollständig akzeptiert; Semantic Compiler Wave abgeschlossen.

## Entwicklungsgrenze

Normale Entwicklung springt nicht mehr in BA0 bis BA9 zurück. Änderungen an
Foundation, Registry, Pässen, IR, Semantik, ABI oder Ownership benötigen ein
neues RFC. Unternehmen dürfen die Architektur nur validieren und keine
Sonderlogik erzwingen.

Die nächste Phase heißt Productization Layer. BA10 – Artifact ABI und Renderer
Isolation – bleibt bis zu einem separaten Operator-Go nicht autorisiert und
wurde durch diesen Freeze nicht begonnen. `release_ready=false` und
`publication_allowed=false` bleiben bestehen.

## Verifikation

```bash
.venv/bin/python scripts/ops/verify_semantic_compiler_wave_freeze.py \
  --product-repo ../company-dossier-lab --json
```

Der Verifier prüft Tag-Ziel, Foundation-/Registry-Locks, Pass-Kette,
IR-Schemasatz, semantischen Source-Set, Evidence-ZIP, Product-Commit und die
unveränderte Canary-Baseline fail-closed.
