# Room16 BA11 — Canary Registry Design

## Vertragsidentität

Vorgeschlagener Vertrag: `room16.canary_registry@1`.

Die Registry ist Research-owned, kanonisch serialisiert über
`room16.foundation.canonical_json@1` und SHA-256-hashgebunden. Product und
spätere Release-Surfaces dürfen ausschließlich einen verifizierten Read-only-
Snapshot konsumieren.

## Registry Envelope

```json
{
  "contract_id": "room16.canary_registry",
  "contract_version": 1,
  "registry_version": "1.0.0",
  "owner": "research_compiler",
  "canonical_serialization": "room16.foundation.canonical_json@1",
  "hash_algorithm": "sha256",
  "entries": [],
  "registry_sha256": "<self-hash ohne registry_sha256>"
}
```

## Canary Entry

Jeder Eintrag enthält mindestens:

| Feld | Vertrag |
|---|---|
| `canary_id` | stabile, opaque, ticker-neutrale ID; unveränderlich und registryweit eindeutig |
| `canary_type` | `regression`, `archetype`, `holdout` oder `release_candidate` |
| `archetype` | versionierte Archetype-ID oder `unclassified`; keine Sonderlogik |
| `source_identity` | strukturierte Emittenten-, Instrument-, Markt-, As-of- und Archividentität |
| `immutable_source_sha256` | exakter Hash des akzeptierten Source Archives |
| `semantic_wave_lock` | exakter Semantic-Wave-Version-Lock |
| `artifact_abi_lock` | exakter BA10-/Artifact-ABI-Freeze-Lock |
| `accepted_bundle_sha256` | kanonischer Bundle-Hash |
| `accepted_renderer_state` | Status, Renderer-Artefakt-Hash und No-New-Truth-Nachweis |
| `baseline_version` | monoton steigende SemVer innerhalb derselben `canary_id` |
| `freeze_state` | `unfrozen`, `candidate`, `frozen`, `superseded`, `stale` |
| `accepted_debt` | sortierte Referenzen auf Debt-Ledger-Einträge und deren Hashes |
| `promotion_state` | aktueller Lifecycle-Zustand plus Referenz auf Promotion Evidence |
| `review_state` | unabhängiger Review- und Operator-Approval-Status |

Empfohlene additive Felder:

- `registry_foundation_lock`
- `foundation_lock`
- `consumer_trust_lock`
- `renderer_contract_lock`
- `source_contract_lock`
- `freeze_record_ref`
- `previous_baseline_ref`
- `coverage_profile_ref`
- `created_at`
- `entry_sha256`

## Source Identity

`source_identity` darf einen Ticker enthalten, aber Governance darf ihn nicht
auswerten. Der Mindestvertrag lautet:

```json
{
  "issuer_identity": "<stable issuer id>",
  "instrument_identity": "<stable instrument id>",
  "ticker": "<descriptive only>",
  "market": "<MIC or explicit market id>",
  "as_of_date": "YYYY-MM-DD",
  "source_archive_name": "<name>",
  "source_contract": "<contract id@major>"
}
```

Entscheidungen werden ausschließlich über `canary_id`, `canary_type`, Locks,
Hashes, Coverage Profile und Review-State getroffen. Regeln wie
`if ticker == "WM"` sind unzulässig.

## Accepted Renderer State

```json
{
  "state": "accepted",
  "rendered_artifact_set_sha256": "<sha256>",
  "source_bundle_sha256": "<sha256>",
  "no_new_truth_verified": true,
  "renderer_generated_facts": 0,
  "renderer_generated_claims": 0,
  "renderer_generated_decisions": 0,
  "release_ready": false,
  "publication_allowed": false
}
```

Jeder abweichende Bundle-Hash, fehlende Renderer-Lineage oder neu erzeugte
fachliche Wahrheit blockiert den Eintrag fail-closed.

## Registry-Invarianten

1. `canary_id` wird nie wiederverwendet.
2. Ein Baseline-Record wird nie in-place geändert.
3. `baseline_version` darf nur über den Promotion-Lifecycle steigen.
4. Source-, Semantic-, ABI-, Consumer- und Renderer-Locks werden gemeinsam
   verglichen.
5. Ein fehlender oder unbekannter Lock bedeutet `stale`, nicht PASS.
6. Accepted Debt ist vollständig vorwärtsgebunden.
7. Ein `frozen` Entry braucht einen gültigen `room16.canary_freeze@2`-Record.
8. `superseded` löscht den Vorgänger nicht.
9. Registry-PASS setzt weder Release- noch Publication-Flags.
10. Ein Product-Mirror darf keine Entry- oder Registry-Hashes prägen.

## Migration der bestehenden drei Canaries

Die erste BA11-Implementierung darf die bestehenden WM-/COST-/ABT-Hashes nur
als unveränderte Genesis-Einträge referenzieren. Die neuen `canary_id`-Werte
werden bei der Implementierung einmalig durch einen generischen, dokumentierten
ID-Generator erzeugt und mit einem Import-Receipt an die bestehenden Source-,
Bundle-, Renderer-, Stage-A- und BA10-Freeze-Records gebunden.

Der Genesis-Import ist keine Promotion und kein Rebaseline. Alle bestehenden
Hashes müssen bytegleich bleiben; jede Abweichung blockiert den Import.
