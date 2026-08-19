# Room16 BA11 — Promotion Governance

## Lifecycle

```text
DEVELOPMENT
  → SHADOW
  → CANDIDATE
  → INDEPENDENT_REVIEW
  → OPERATOR_APPROVAL
  → PROMOTED
  → FROZEN
```

Jeder Übergang erzeugt ein hashgebundenes Event. Zustände werden nicht durch
das Umschreiben eines einzelnen Statusfelds simuliert.

## DEVELOPMENT

- Lokaler, nicht autoritativer Arbeitsstand.
- Darf keine akzeptierte Registry- oder Freeze-Datei verändern.
- Muss eine deklarierte Change Classification und Impact-Fläche besitzen.
- `promotion_allowed=false`.

## SHADOW

- Führt den Candidate gegen die aktive Frozen Baseline aus.
- Bindet exakt dieselben Locks oder dokumentiert den Breaking-Change-Pfad.
- Erzeugt vollständige Compare-, Regression-, Debt- und Stale-Evidence.
- Ein Diff ist ein Befund, kein Rebaseline-Grund.

## CANDIDATE

- Content-addressed, reproduzierbares und manifestiertes Paket.
- Bindet Vorgänger-Freeze, Change Class, Source, Bundle, Renderer, Locks,
  Accepted Debt und alle Tests.
- Darf nach Erzeugung nicht mutiert werden.
- `release_ready=false`, `publication_allowed=false`.

## INDEPENDENT_REVIEW

- Review bezieht sich auf den exakten Candidate-Hash.
- Ergebnis ist `accepted`, `changes_required` oder `rejected`.
- `changes_required` erzeugt einen neuen Candidate; der alte bleibt erhalten.
- Reviewer-Evidence ersetzt keine Operator-Approval.

## OPERATOR_APPROVAL

- Explizite Entscheidung für genau den akzeptierten Candidate- und Review-
  Hash.
- Approval-Scope ist ausschließlich Canary-Promotion.
- Kein implizites Release-, Public-, Legal- oder Paid-Go.

## PROMOTED

- Ein gültiger Promotion-Event wurde erzeugt und verifiziert.
- Die neue Baseline darf noch nicht als dauerhaft Frozen gelesen werden,
  solange der Freeze-v2-Record und Registry-Snapshot nicht atomar verifiziert
  sind.

## FROZEN

- Freeze-v2-Record, Registry Entry, Vorgängerreferenz, Debt-Set und alle Locks
  stimmen.
- Der frühere Freeze wird über einen separaten Supersession-Record referenziert.
- Nach Freeze ist die Baseline unveränderlich.

## Fehlerpfade

| Ereignis | Ergebnis |
|---|---|
| Regression in SHADOW | Candidate blockiert; aktive Baseline bleibt unverändert |
| Breaking Change ohne RFC | fail-closed; kein Candidate |
| Review `changes_required` | zurück zu DEVELOPMENT mit neuem Candidate-Hash |
| Review `rejected` | Rejection-Record; aktive Baseline bleibt unverändert |
| Operator lehnt ab | Rejection-Record; keine Promotion |
| Freeze-Verifikation schlägt fehl | Zustand bleibt nicht promoted/frozen |
| Debt fehlt | fail-closed; kein Review-/Approval-Übergang |
| Stale Baseline | kein PASS; Rereview-/Neufreeze-Pfad erforderlich |

## Harte Regel: kein automatisches Rebaselining

Bei Regression gilt immer:

1. aktive Frozen Baseline nicht verändern,
2. Regression und Change Classification dokumentieren,
3. Root Cause bestimmen,
4. Fix oder bewusstes Breaking-Change-RFC erzeugen,
5. vollständigen Lifecycle erneut durchlaufen.

Verboten sind „Update Golden“, „accept current output“, Snapshot-Refresh oder
Hash-Neuschreiben als automatischer Test-Fix.

## Rollen- und Authority-Grenze

- Research besitzt Registry-, Compare-, Promotion- und Freeze-Evidence.
- Product ist hashverifizierender Consumer und darf keine Promotion prägen.
- Independent Review akzeptiert oder verwirft Evidence.
- Operator autorisiert die Baseline-Promotion.
- Release-/Legal-/Editorial-/Public-/Paid-Gates bleiben separate Authorities.
