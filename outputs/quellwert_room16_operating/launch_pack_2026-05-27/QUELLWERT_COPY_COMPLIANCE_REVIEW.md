# Quellwert Copy Compliance Review

- Generated at: `2026-05-27T21:53:31+02:00`
- Status: `pass_with_operator_legal_gate`

## Checks

| Check | Status | Ergebnis |
|---|---|---|
| Non-Advice sichtbar | `PASS` | öffentliche Seiten enthalten Nicht-Beratungs-Sprache |
| Harte Trading-Tokens | `PASS` | keine Treffer für Buy/Sell/Kaufen/Verkaufen/Kursziel/Modellportfolio |
| Hidden Cases | `PASS` | NVDA/MU bleiben versteckt |
| Payment/Checkout | `PASS` | kein Checkout im Launch Pack aktiviert |
| Legal Finality | `WARN` | Impressum/Datenschutz sind Preview-Gate, nicht finale Rechtsprüfung |
| Investment-Recommendation Risk | `WARN` | Paid Research braucht vor Aktivierung gesonderten Compliance-Review |

## Verifier Evidence

- `npm run verify:quellwert-public-catalog-contract`: `PASS`
- `npm run verify:quellwert-softlaunch-readiness`: `PASS`
- Static hard-signal scan: `PASS`

## Copy-Regeln Für Launch

Erlaubt:

- `Research-Notiz`
- `Unternehmensanalyse`
- `quellenbasiert`
- `Methodik`
- `Watchlist-Kontext`
- `offene Review-Punkte`
- `keine Anlageberatung`

Nicht erlaubt:

- `Jetzt kaufen`
- `Jetzt verkaufen`
- `Kursziel`
- `Modellportfolio`
- `Renditeversprechen`
- `persönliche Empfehlung`
- `konkrete Portfolio-Aktion`

## Verdict

Die Copy ist für Operator Review und private Preview-Vorbereitung geeignet. Sie ist noch kein Go für externe Veröffentlichung, Payment oder paid investment-recommendation-like Output.
