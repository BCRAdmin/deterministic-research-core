# Room16 BA11 — Accepted Debt Model

## Ziel

Accepted Debt ist Teil der Baseline-Identität. Es darf bei einer neuen
Baseline weder verschwinden noch still umbenannt, zusammengelegt oder als
„durch neuen Snapshot erledigt“ behandelt werden.

## Debt Entry

```json
{
  "debt_id": "<stable id>",
  "origin": {},
  "debt_type": "accepted_nonblocking_debt",
  "severity": "low",
  "accepted_at": "<RFC3339>",
  "rationale": "<bounded rationale>",
  "affected_canaries": ["<canary_id>"],
  "carried_forward": true,
  "resolved_by": null,
  "rereview_trigger": [],
  "entry_sha256": "<self-hash>"
}
```

Pflichtfelder sind `debt_id`, `origin`, `severity`, `accepted_at`, `rationale`,
`affected_canaries`, `carried_forward`, `resolved_by` und
`rereview_trigger`.

## Typen

- `accepted_nonblocking_debt`: bewusst akzeptierter, nicht blockierender Rest.
- `environmentally_unverified`: offengelegte externe Reproduktionsgrenze;
  keine behauptete Auflösung.
- `transition_debt`: zeitlich begrenzte Architektur- oder Migrationsschuld.
- `review_limitation`: begrenzter Review-Scope oder nicht prüfbare Fläche.

Ein Typwechsel braucht einen neuen verknüpften Entry und Review-Evidence; der
alte Entry bleibt erhalten.

## Carry-Forward-Regel

Für jede Candidate-Baseline wird berechnet:

```text
required_debt = previous_active_debt - validly_resolved_debt
candidate_debt must be a superset of required_debt
```

Ein Debt Entry gilt nur als aufgelöst, wenn `resolved_by` einen
content-addressed Resolution Record referenziert, der mindestens enthält:

- Root Cause,
- Fix-/Entscheidungs-Evidence,
- Negativ-Fixture und Reintroduction Gate,
- Canary-Regression,
- unabhängigen Rereview, falls vom Entry gefordert,
- Operator-Entscheidung, falls die ursprüngliche Acceptance operator-gated war.

Fehlt ein Entry ohne gültige Resolution Evidence, lautet der stabile
Diagnostic Code `CANARY_ACCEPTED_DEBT_DISAPPEARED` und die Promotion blockiert.

## Aktueller Genesis-Debt-Bestand

### RC1FE5-015

- Typ: `accepted_nonblocking_debt`
- Ursprung: Final Acceptance `8cf064d75c8c-20260814-115448`
- Inhalt: Appendix-/Evidence-Browsing-UX ist vollständig und lesbar, aber
  keine ideale Navigationsfläche.
- Betroffene Canaries: die drei importierten Genesis-Canaries.
- Carry Forward: verpflichtend, bis eine hashgebundene Resolution Evidence
  plus erforderlicher Rereview vorliegt.

### RC1FE5-016

- Typ: `environmentally_unverified`
- Ursprung: Final Acceptance `8cf064d75c8c-20260814-115448`
- Inhalt: exakte fremde Kalender-, Renderer- und Font-Reproduktion bleibt
  umgebungsabhängig unverifiziert.
- Der Eintrag darf nicht als „accepted resolved debt“ umetikettiert werden.
- Er bleibt als Review-Limitation sichtbar und besitzt eigene Rereview-Trigger.

## Rereview-Trigger

Mindestens:

- Änderung der betroffenen Renderer-/Environment-Fläche,
- neue Evidence, die die Schuld auflöst oder verschärft,
- Severity-Erhöhung,
- neue betroffene Canary,
- Promotion einer Baseline, die das beobachtete Verhalten verändert,
- Breaking Change an einem referenzierten Contract.

## Hashbindung

Die sortierte Menge der aktiven `entry_sha256`-Werte bildet
`accepted_debt_set_sha256`. Dieser Hash ist Bestandteil von Registry Entry,
Promotion Candidate und Freeze v2. Dadurch kann Debt nicht ohne Änderung der
Baseline-Identität verschwinden.
