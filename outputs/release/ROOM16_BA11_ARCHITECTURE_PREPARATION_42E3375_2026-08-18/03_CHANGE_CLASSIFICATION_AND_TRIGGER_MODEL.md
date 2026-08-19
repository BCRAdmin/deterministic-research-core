# Room16 BA11 — Change Classification and Trigger Model

## Klassen

### ORDINARY_CHANGE

Eine Änderung außerhalb eingefrorener semantischer Flächen, die alle Locks,
Source Archives, Bundles, Decisions, sichtbaren semantischen Inhalte und
Accepted-Debt-Sätze unverändert lässt. Beispiele: reine Dokumentation,
vergleichsneutrale Telemetrie oder nachweislich semantikfreie Darstellung.

Pflicht: automatischer Compare und vollständige Canary-Regression. Ein FAIL
stoppt; es gibt kein automatisches Rebaseline.

### REVIEW_REQUIRED_CHANGE

Eine additive oder betriebliche Änderung mit potenziell größerem Impact
Radius, obwohl kein eingefrorener Contract bewusst geändert wird. Beispiele:
neue Diagnoseklasse, Dependency-/Runtime-Wechsel, neuer Renderer-Backend-Pfad
bei identischer Semantik oder neuer Canary-/Archetype-Eintrag.

Pflicht: automatischer Compare, fail-closed bei Abweichung, menschliche
Risikoprüfung und explizite Promotion-Entscheidung. RFC nur dann, wenn die
Prüfung eine eingefrorene Fläche berührt oder Contract-Semantik ändert.

### BREAKING_CHANGE

Jede Änderung an BA0–BA10, Foundation, Registry Foundation, Semantic Wave,
IR-Schemata oder -Bedeutung, Parser-/Tabellenverhalten, Metric-/Formel-
Bedeutung, Evidence-/Claim-/Decision-Semantik, Artifact ABI, Consumer Trust,
Renderer-Semantik, Source Contract oder bestehender Diagnostic-Bedeutung.

Pflicht: fail-closed, unabhängiger Rereview, neues RFC, explizite
Versionierungsentscheidung und neues Operator-Go. Baseline-Promotion ist erst
nach dem vollständigen Lifecycle möglich.

## Trigger-Matrix

| Trigger | Standardklasse | Automatic Compare | Fail closed | Human Rereview | Neues RFC | Neue Version | Baseline-Promotion |
|---|---|---:|---:|---:|---:|---:|---|
| Foundation change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Registry Foundation change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Semantic Wave change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| IR schema change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Parser/table behavior change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Metric/formula meaning change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Evidence/claim meaning or lineage change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Decision logic change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Artifact ABI change | `BREAKING_CHANGE` | ja | ja | ja | ja | Major/Minor nach Compatibility-Analyse | nur nach vollständigem Lifecycle |
| Consumer trust change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Renderer-visible semantic change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Rein presentation-only renderer change | `ORDINARY_CHANGE`; Upgrade bei Diff | ja | bei jeder semantischen oder Lineage-Abweichung | nur bei Upgrade/Unsicherheit | nein, solange BA10-Locks unverändert | nein | bestehende Baseline bleibt; keine Promotion nötig |
| Source contract change | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Neue Diagnostic-/Root-Cause-Klasse | `REVIEW_REQUIRED_CHANGE` | ja | ja | ja | wenn Gate-, Severity- oder Contract-Semantik betroffen | mindestens additive Contract-Version | nur nach Review und Operator-Approval |
| Änderung bestehender Diagnostic-Bedeutung | `BREAKING_CHANGE` | ja | ja | ja | ja | ja | nur nach vollständigem Lifecycle |
| Neuer Canary-/Archetype-Eintrag bei unveränderten Locks | `REVIEW_REQUIRED_CHANGE` | ja | ja | ja | nein, wenn BA11-Vertrag unverändert | neue Baseline-Version | nach Lifecycle erlaubt |

## Automatische Vergleiche

Jeder Compare bindet mindestens:

- immutable Source SHA-256,
- Foundation- und Registry-Lock,
- Semantic-Wave-Lock,
- IR-Schema- und Pass-Manifest-Hash,
- Artifact-ABI-/BA10-Freeze-Lock,
- Consumer-Trust- und Renderer-Contract-Lock,
- Bundle- und Renderer-Artefakt-Hash,
- Facts, Metrics, Formulae, Evidence, Claims, Decisions, Diagnostics, Verdict,
- Accepted-Debt-Set-Hash,
- Release-/Publication-Negativgrenzen.

Ein unbekannter, fehlender oder nicht vergleichbarer Wert ist kein neutraler
Diff, sondern blockiert als `stale_or_unverifiable`.

## Klassifikationsregeln

- Die höchste anwendbare Klasse gewinnt.
- Ein Ordinary Change wird bei jeder semantischen, Hash-, Lock-, Debt- oder
  Diagnostic-Abweichung automatisch hochgestuft.
- Kein Klassifikator darf über Ticker oder Unternehmensnamen verzweigen.
- Ein Breaking Change darf niemals durch ein grünes Canary-Ergebnis allein
  wieder freigegeben werden.
- Eine Promotion ändert ausschließlich Canary-Baseline-Governance. Sie ist
  weder Release-Go noch Publication-Go.
