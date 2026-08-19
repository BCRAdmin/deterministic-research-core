# Room16 BA11 — Stale Detection Model

## Grundregel

`stale` bedeutet: Eine akzeptierte Baseline kann die aktuell ausgeführte
Systemkonfiguration nicht mehr vollständig und exakt repräsentieren. Stale ist
niemals PASS und darf weder durch einen grünen Teiltest noch durch einen
fehlenden Compare still ignoriert werden.

## Stale-Trigger

Eine Baseline wird mindestens stale, wenn:

- Registry Foundation Lock nicht mehr exakt aktuell ist,
- Semantic Wave Lock geändert wurde,
- Artifact ABI/BA10 Freeze Lock geändert wurde,
- Source Contract oder Source Identity Contract geändert wurde,
- Freeze-v2-Record fehlt, beschädigt oder nicht verkettet ist,
- Consumer Trust Lock geändert wurde,
- Renderer Contract oder No-New-Truth-Grenze geändert wurde,
- Foundation Lock, IR-Schema-Hash oder Pass-Manifest-Hash abweicht,
- Accepted-Debt-Set nicht vollständig vergleichbar ist,
- Registry Entry oder Product-Mirror nicht hashgleich ist,
- ein erforderliches Artefakt oder Receipt fehlt,
- eine neue Diagnostic-/Root-Cause-Klasse die Aussagekraft der Baseline
  verändert,
- Source Archive, Bundle oder Renderer-Artefakt nicht mehr dem Freeze
  entspricht.

## Detection Record

```json
{
  "contract_id": "room16.canary_stale_detection",
  "contract_version": 1,
  "canary_id": "<id>",
  "freeze_reference": "<freeze id>",
  "status": "stale_blocked",
  "reasons": [
    {
      "surface": "semantic_wave_lock",
      "expected": "<hash>",
      "observed": "<hash>",
      "diagnostic_code": "CANARY_SEMANTIC_LOCK_MISMATCH"
    }
  ],
  "detected_at": "<RFC3339>",
  "evidence_sha256": "<sha256>",
  "stale_record_sha256": "<self-hash>"
}
```

## Zustandswirkung

Bei `stale_blocked` gelten zwingend:

- `canary_pass=false`
- `automatic_compare_status=blocked`
- `promotion_allowed=false`
- `release_registry_eligible=false`
- `release_ready=false`
- `publication_allowed=false`
- `human_rereview_required=true`

Ein System darf nicht auf die letzte bekannte grüne Ausführung zurückfallen
und sie als aktuellen PASS anzeigen.

## Auflösung

Staleness endet nur durch einen verifizierten Vorgang:

1. Byteidentische Wiederherstellung des erwarteten Locks/Artefakts plus
   Recovery Evidence, wenn kein Contract geändert wurde; oder
2. neue Change Classification, Compare Evidence, unabhängiger Review,
   Operator-Approval, Promotion und Freeze-v2-Record.

Ein bloßes Neuschreiben des erwarteten Hashes ist verboten.

## Priorität

Stale Detection läuft vor semantischem Canary-Vergleich. Ein semantischer
PASS unter falschen Locks ist wertlos und wird als
`CANARY_STALE_BASELINE_BLOCKED` ausgegeben.
