# Room16 BA11 — Current Canary State

## Autoritative Freeze-Koordinaten

| Fläche | Aktueller akzeptierter Stand |
|---|---|
| Compiler Foundation | `1.0.0`; Lock `8b9b7b2f59aa2cfed8280389f14c0e4edd11846d56c1d78e0dbf2c574da7d518` |
| Registry Foundation | `1.1.0`; Authority `55585f2242f32da4cc401455cd3186a97bf74f2c4a7feb5078e00d6a6e1ea5fb` |
| Semantic Compiler Wave | `1.0.0`; Lock `62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9` |
| Artifact ABI | `room16.compiler_artifact_bundle@1`; Schema `1.2.0` |
| BA10 Freeze | `1.0.0`; Lock `29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e` |
| Authority Bundle | v3, nur einseitige Compatibility View |
| BA10 Research | `e10c8d4454c9ebeef42a7e8f1021aff291225e8c` |
| BA10 Product | `de0dfbde1d7e14d081b8da27933f7164c88d0d12` |
| BA10 Tag | `room16-ba10-artifact-abi-renderer-v1.0.0` |
| Status | BA10 `ACCEPTED / FROZEN`; BA11/BA12 nicht autorisiert; Release/Publication blockiert |

## Identitätsgrenze

Der heutige Vertrag `room16.cross_company.canary_baseline@1` besitzt kein
explizites `canary_id`. Seine drei Einträge werden nur über die Ticker-Schlüssel
`WM`, `COST` und `ABT` sowie den gemeinsamen Release
`8cf064d75c8c-20260814-115448` identifiziert. Die folgenden
`implicit_current_identity`-Werte dokumentieren daher den Ist-Zustand; sie sind
keine neu eingeführten IDs und dürfen nicht als Implementierung gelesen werden.

## Canary-Inventar

| Feld | WM | COST | ABT |
|---|---|---|---|
| `implicit_current_identity` | `cross_company_baseline/8cf064d7/WM` | `cross_company_baseline/8cf064d7/COST` | `cross_company_baseline/8cf064d7/ABT` |
| Ticker | `WM` | `COST` | `ABT` |
| Aktuelle Rolle | automatische Regression-Canary; Waste-/Environmental-Services-Archetype | automatische Regression-Canary; Membership-Retail-Archetype | automatische Regression-Canary; Diversified-Medical-Devices-/Diagnostics-Archetype |
| Archetype | `WASTE_ENVIRONMENTAL_SERVICES` | `MEMBERSHIP_RETAIL` | `DIVERSIFIED_MEDICAL_DEVICES_DIAGNOSTICS` |
| As-of | `2026-08-11` | `2026-08-13` | `2026-08-13` |
| Source Archive SHA-256 | `a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72` | `b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4` | `0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45` |
| Accepted Bundle SHA-256 | `71bc2f1dae367ecfe83f8f84f7a5d4eceffca07954709f2ea4d3caab655ff339` | `2c6a35f23011faa7ef1b6f1a401fb184d2b0f602766836df05a6ba66f94bbdd4` | `48a39cf7537d4ed1f807d3a532173847192d6bfe805cd12fd3f5842b8d26383a` |
| Bundle ZIP SHA-256 | `deead15c358590c8e5bccfac922dd860db7f28ca3edde334a7daf8a1377ab843` | `feced2406db17e64c52602d9e4a80d22b4781a2e48f209ee2ee5141a9003e486` | `50c2d76bc9428b3ceb1d62db0230764e099a32cf755f8cf2cc27ce07b36f53b6` |
| Renderer ZIP SHA-256 | `cad4e625c88b10df8fe5bce548356891e33ed3a0cd14f9e12ea1f218c15f0cc9` | `ae0479643893f7c15883d754dce993f59bfbd887b4abb20f3762b3495d211607` | `c3788a5ed4d175ddb444c69d6b478c91bb26f6e8159200a87a454912528934dd` |
| Renderer Acceptance | `accepted`; No-New-Truth verifiziert | `accepted`; No-New-Truth verifiziert | `accepted`; No-New-Truth verifiziert |
| Stage-A Research Baseline | `f691c4584ac9f03f6e1d459ac3c37cbe5ce12716` | identisch | identisch |
| Stage-A Product Baseline | `93416c689d4ae8c25c478a502157640f7714cacb` | identisch | identisch |
| BA10 Accepted Research Baseline | `e10c8d4454c9ebeef42a7e8f1021aff291225e8c` | identisch | identisch |
| BA10 Accepted Product Baseline | `de0dfbde1d7e14d081b8da27933f7164c88d0d12` | identisch | identisch |
| Semantic Wave Lock | `62867ad7…30f9` | `62867ad7…30f9` | `62867ad7…30f9` |
| BA10 Freeze Lock | `29bc0bf2…bc8e` | `29bc0bf2…bc8e` | `29bc0bf2…bc8e` |

Die Trennung zwischen Stage-A-Baseline und BA10-Baseline ist wesentlich:
Stage A bindet die unveränderten Source Archives und den historischen
Cross-Company-Kandidaten. BA10 bindet die daraus erzeugten Artifact Bundles,
Renderer-Artefakte und Consumer-Trust-Grenzen. BA11 darf beide Ebenen nur
referenzieren, nicht zusammenziehen oder überschreiben.

## Bestehende Freeze- und Release-Artefakte

- Product-Baseline-Record:
  `config/room16_canary_baseline.json`, Datei-SHA-256
  `88795b625b2d9ab892b559d98b6d4d0a0c79364088fe7376dc49a3b8bd796d7f`.
- Cross-Company-Release:
  `ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448`;
  Versionslock
  `8cf064d75c8cc3bf23f947189f25ee2de3f2bd0c5356b51d5d7f37d631085333`.
- Final Acceptance:
  `ROOM16_CROSS_COMPANY_FINAL_ACCEPTANCE_8CF064D7_2026-08-14.zip`, SHA-256
  `de4a6f50c13b668b6a47cc51ea11a0543696a17910ddbb73c2ae798c22ac8a97`.
- Semantic-Wave-Freeze:
  `research_agent/semantic_compiler/freeze/semantic_compiler_wave_freeze_v1.json`.
- BA10 Human Freeze Record:
  `docs/compiler_foundation/BA10_ARTIFACT_ABI_RENDERER_FREEZE_V1.md`.
- BA10 Machine Freeze Record:
  `research_agent/productization/freeze/ba10_artifact_abi_renderer_freeze_v1.json`.
- BA10 Final Closure Evidence:
  `ROOM16_RFC_0005_R3_BA10_FINAL_CLOSURE_E10C8D44_2026-08-18.zip`, SHA-256
  `65055d2db0313aa713ff8af043815827aff960ca52a30d9eb0fab2124b0f8814`.
- Research-eigenes Receipt Set:
  `room16.compiler_artifact_bundle_receipt_set@1`, Set-Hash
  `bf2bb816d26771c50d4cce82f36a8d7d7e79f70087bd601f576ba536a0ccde4f`.

## Accepted Debt und offene Review-Grenze

- `RC1FE5-015`: akzeptierte nicht blockierende Appendix-/Browsing-UX-Schuld.
- `RC1FE5-016`: umgebungsabhängige Kalender-/Renderer-/Font-Reproduktion
  bleibt unverifiziert. Sie ist keine stillschweigend akzeptierte Auflösung.
- `release_ready=false` und `publication_allowed=false` bleiben in allen
  Acceptance- und Freeze-Schichten erhalten.

## Bestehende hard-coded Canary-Logik

Die folgenden Flächen sind im Ist-Zustand explizit auf WM/COST/ABT gebunden:

1. `room16/core/cross_company_acceptance.py`
   - `REQUIRED_TICKERS = ("WM", "COST", "ABT")`
   - festes Finding-Set, Accepted Debt und Manual-Rereview-Trigger
   - akzeptiert nur exakt diese drei Candidate-Hashes.
2. `room16/core/cross_company_release.py`
   - `REQUIRED_TICKERS = ("WM", "COST", "ABT")`
   - lehnt andere Ticker als Cross-Company-Candidate ab.
3. `research_agent/semantic_compiler/semantic_wave/release_gates.py`
   - erwartet exakt die Menge `{WM, COST, ABT}`
   - blockiert ticker-spezifische Registry-Namespaces bereits fail-closed.
4. `research_agent/semantic_compiler/semantic_wave/legacy_replay.py`
   - beschreibt und verarbeitet den Frozen-WM/COST/ABT-Shadow-Replay.
5. `scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py`
   - iteriert explizit über `("WM", "COST", "ABT")` und bindet deren Source-,
     Bundle- und Renderer-Hashes.
6. BA10 Freeze Record und Receipt Set
   - enthalten drei explizite Einträge und keine generische Canary-Registry.

Diese Hardcodings sind im eingefrorenen Bestand korrekt und dürfen von BA11
nicht verändert werden. BA11 muss additiv eine generische Registry einführen;
eine spätere Migration bestehender Prüfer ist ein gesonderter, verifier-
gebundener Implementierungsschritt.

## Bestehende Promotion- und Regression-Logik

- Ordinary Changes: automatisierte Regression gegen WM/COST/ABT.
- Manual Rereview: bei Canary-FAIL, semantischem Schema- oder Metric-Registry-
  Bruch, Parser-/Tabellenarchitekturwechsel, Numeric-/Release-Gate-Redesign
  oder neuem Archetype mit neuer Root-Cause-Klasse.
- Cross-Company-Closure: pro Finding sind Negativ-Fixture, korrigiertes
  Fixture, Real-Candidate, Reintroduction Gate und Cross-Company-Regression
  hashgebunden erforderlich.
- Stage-A-Acceptance: validiert externes Review, Manifest, Commits,
  Versionslock, Candidate-ZIPs und Finding-Set fail-closed.
- Quellwert/Public-Promotion: ist ein separater nachgelagerter Vertrag und
  keine Canary-Rebaseline-Mechanik.

## Architekturdefizit

Es gibt heute keinen generischen Lifecycle `DEVELOPMENT → … → FROZEN`, keinen
append-only Freeze-v2-Vertrag, keine eigene Stale-Semantik und keine
maschinenlesbare Regel, die Accepted Debt bei jeder neuen Baseline zwingend
vorwärtsbindet. BA11 kann genau diese Lücke schließen, ohne eine akzeptierte
Baseline zu verändern.
