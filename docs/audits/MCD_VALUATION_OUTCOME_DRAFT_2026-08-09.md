# MCD-Bewertungsergebnis: kontrollierter Entwurfsfall

Stand: 9. August 2026

## Zweck

Dieser Fall prüft den neuen providerneutralen Outcome-Vertrag an einem echten,
historischen MCD-Bewertungssnapshot. Er ist ausdrücklich kein bestätigtes
Total-Return-Ergebnis und keine Freigabe für ein Bewertungssignal.

## Gebundener Snapshot

- Ticker: `MCD`
- Bewertungsstichtag: `2025-07-31`
- Snapshot-ID:
  `sha256:1a9eefed16613c94e5572eeeca01de90842c5779ee087ef299aeba8813a4e01b`
- Snapshot-Modus: historischer Point-in-Time-Replay
- Benchmark-Kandidat: `SPY`

## Beobachtungsabdeckung

- MCD: `257` offizielle historische Schlusskursbeobachtungen vom
  31. Juli 2025 bis 7. August 2026
- SPY: `256` offizielle historische Schlusskursbeobachtungen im selben
  Zeitraum
- Gemeinsame zukünftige Beobachtungen im Rechenfenster: `252`
- 252. gemeinsame Beobachtung: `2026-08-04`

Damit ist das Zeitfenster grundsätzlich ausgereift. Room16 berechnet trotzdem
bewusst keine Rendite, weil zeitliche Reife allein die Datenqualität nicht
beweist.

## Korrekte Sperre

Der Entwurf ist `invalidated` und `live_activation_allowed=false`. Die vier
fachlichen Blocker sind:

1. Die sichtbaren Nasdaq-Historien sind nicht als vollständige
   Total-Return-Reihen einschließlich Dividenden und Kapitalmaßnahmen belegt.
2. Die Anbietermethodik ist nicht als eigener Nachweis gebunden.
3. Die Nutzungsrechte für die interne Kalibrierung sind nicht menschlich
   freigegeben und belegt.
4. Eine unabhängige menschliche Prüfung der Daten und ihrer Semantik fehlt.

Die Workbench hat deshalb weder MCD- noch Benchmark-Rendite und auch keine
Überrendite ausgegeben. Ein raw-close-Ergebnis darf nicht versehentlich in die
Kalibrierungsstichprobe gelangen.

## Lokale Evidence

Das vollständige, nicht versionierte Prüfpaket liegt im ignorierten
Room16-Runtime-Bereich:

```text
.runtime/valuation-outcome-workbench/MCD/2025-07-31/nasdaq-close-draft-20260809/
```

Es enthält kopierte Quellreihen, das hash-gebundene v2-Quellenpaket,
Ergebnisvorschau, Workbench-Status und das deutsche Prüfpaket. Die Kursreihen
werden wegen ungeklärter Nutzungsrechte nicht in Git übernommen.

## Nächster echter Freigabeschritt

Für einen verifizierten MCD-Ausgang braucht Room16 keine neue Bewertungsformel,
sondern einen Datenweg, der Total-Return-Semantik und interne Nutzungsrechte
belegt. Danach müssen eine identifizierte Rechtefreigabe und eine davon
getrennte menschliche Datenprüfung als eigene Evidence-Dateien gebunden werden.
Auch ein anschließend gültiges Ergebnis bleibt zunächst ausschließlich
Shadow-Kalibrierung; es aktiviert kein Rating automatisch.
