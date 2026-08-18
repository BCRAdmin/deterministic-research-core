# Room16 BA10 Artifact ABI and Renderer Isolation Freeze v1

Status: **ACCEPTED / FROZEN** seit 2026-08-18.

Der unabhängige BA10-Final-Review hat RFC-0005 und RFC-0005-R3 akzeptiert.
Die Findings `BA10-R2-AR-001` bis `BA10-R2-AR-004` sind geschlossen. Dieser
Record führt ausschließlich den formalen Freeze durch; er ändert weder die
Implementierung noch die Architektur, Canaries oder Unternehmensartefakte.

## Freeze-Koordinaten

| Bestandteil | Eingefrorener Wert |
|---|---|
| BA10-Freeze-Version | `1.0.0` |
| Git-Tag | `room16-ba10-artifact-abi-renderer-v1.0.0` |
| Tag-Objekt | `78c39bf8c69754f717ef03833add898d69da4979` |
| Research-Commit | `e10c8d4454c9ebeef42a7e8f1021aff291225e8c` |
| Product-Commit | `de0dfbde1d7e14d081b8da27933f7164c88d0d12` |
| Artifact ABI | `room16.compiler_artifact_bundle@1` |
| Bundle-Schema | `1.2.0` |
| Semantic Compiler Wave | `1.0.0` |
| Semantic-Version-Lock | `62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9` |
| Compiler Foundation | `1.0.0` |
| Registry Foundation | `1.1.0` |
| Authority Bundle | `v3` als einseitige Compatibility View |
| Freeze-Lock | `29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e` |

Der maschinenlesbare Record liegt unter
`research_agent/productization/freeze/ba10_artifact_abi_renderer_freeze_v1.json`.

## Eingefrorene Verträge

- Consumer Policy:
  `66a08374be21f0a74be0697fd9568edc41e7b5c8462e8f05544ba2cb7cbd2cae`
  bei Datei-Hash
  `5429d749fd86edd2b0d4b4d99aba5472b4e9bec79af3eabd2958bb5136195c11`.
- Receipt Set:
  `bf2bb816d26771c50d4cce82f36a8d7d7e79f70087bd601f576ba536a0ccde4f`
  bei Datei-Hash
  `73b6ad0c7b9754ff30d39ca2b5d735bb77c2d83f32656c38f7ada4bd2faf0897`.
- Exaktes Zehn-Pass-Profil:
  `d0297b368957cb4d12c89f290f1fe4cddb0bfdfcdee8d3bb5be304ca1c7aa48c`.
- Pflichtartefakt-Profil mit 18 Artifact Kinds:
  `dbb9155202d0d3dd58e1ebd9c250966725d2213598ae9729c4c46766e4c501d4`.

Research bleibt alleiniger fachlicher Owner. Product konsumiert ausschließlich
das hashverifizierte CompilerArtifactBundle. Renderer dürfen Darstellung und
Layout erzeugen, aber keine Facts, Metrics, Claims, Evidence, Decisions oder
Ratings verändern oder neu erzeugen. Authority Bundle v3 bleibt eine
einseitige Compatibility View aus dem CompilerArtifactBundle; der inverse Weg
zur Compiler-Wahrheit ist verboten.

## Akzeptierte Canaries

| Canary | Source SHA-256 | Bundle SHA-256 | Renderer |
|---|---|---|---|
| WM | `a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72` | `71bc2f1dae367ecfe83f8f84f7a5d4eceffca07954709f2ea4d3caab655ff339` | akzeptiert |
| COST | `b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4` | `2c6a35f23011faa7ef1b6f1a401fb184d2b0f602766836df05a6ba66f94bbdd4` | akzeptiert |
| ABT | `0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45` | `48a39cf7537d4ed1f807d3a532173847192d6bfe805cd12fd3f5842b8d26383a` | akzeptiert |

Die Canaries validieren die eingefrorene Architektur. Sie erzeugen keine
Unternehmenssonderlogik und dürfen nicht als Anlass für Architekturänderungen
verwendet werden.

## Akzeptanz- und Migrationsstatus

- `rfc_0005_accepted=true`
- `rfc_0005_r3_accepted=true`
- `independent_acceptance=pass`
- `production_trust_api_closure=true`
- `exact_pass_execution_profile_closure=true`
- `required_artifact_profile_closure=true`
- `full_regression_closure=true`
- `product_parallel_truth_removed_in_canonical_path=true`
- `legacy_bridge_active=true`
- `full_renderer_cutover=false`
- `source_native_fact_generation=false`
- `release_ready=false`
- `publication_allowed=false`
- `ba11_authorized=false`
- `ba12_authorized=false`

## Änderungsregel nach dem Freeze

Änderungen am Verhalten des CompilerArtifactBundle-Vertrags, an der Product-
Consumer-Trust-Grenze, der Renderer-Wahrheitsgrenze, dem Pass Execution
Profile, dem Required Artifact Profile oder der Authority-v3-Bridge-Semantik
benötigen ab jetzt ein ausdrückliches RFC und eine passende
Versionierungsentscheidung. Ein stiller Patch, ein Renderer-Fix oder eine
Unternehmenssonderregel darf diese Grenze nicht verändern.

## Verifikation

```bash
.venv/bin/python scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py \
  --product-repo ../company-dossier-lab --json
```

Der Verifier prüft Tag und Commits, Foundation-, Registry- und Semantic-Locks,
Artifact ABI und Schema, alle vier Policy-/Receipt-/Profile-Locks, eingefrorene
Research-/Product-Quellen, die drei Source- und Bundle-Hashes, Renderer-
Akzeptanz sowie sämtliche negativen Statusgrenzen fail-closed.

Nach diesem Freeze wird keine BA11-Vorbereitung begonnen.
