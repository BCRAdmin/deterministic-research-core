# Room16 P5 – technischer Abschluss

Stand: 10. August 2026

P5 erweitert nicht den Analyse-Scope. Die Stufe stellt eine belastbare, weiterhin
kostenlose Betriebsbasis für mehr Titel bereit und hält alle fachlichen Grenzen
sichtbar.

## Technisch fertig

- Eine kanonische Capability-Registry trennt Markt, Provider, Kostenart,
  Quellenrolle, Datenbedeutung und Integrationsstatus.
- US/SEC und Ungarn/BSE sind unterstützt. Japan/EDINET und
  Südkorea/OpenDART werden erkannt, starten aber keine Analyse.
- `auto` bleibt immer beim kostenlosen Nasdaq-Kursweg. Ein vorhandener
  Massive-Schlüssel aktiviert Massive nicht mehr still.
- Der Scale-Plan akzeptiert höchstens 1.000 eindeutige Instrumente, läuft
  seriell, ist rate-limitiert, isoliert Fehler und kann aus atomarem
  Runtime-Zustand fortgesetzt werden.
- Eine Ausführung benötigt den exakten SHA-256-Wert des zuvor erzeugten Plans.
  Ohne diese Bestätigung wird kein Titel gestartet.
- Scale-Runs dürfen weder Modelle noch Publishing, externe Automationen oder
  kostenpflichtige Provider auslösen.
- Der Änderungsprüfer vergleicht vorhandene Authority-Manifeste und erzeugt nur
  eine menschliche Review-Aufgabe. Er startet nichts selbst.
- Die Produkt-App liest eine kryptografisch gebundene Kopie der kanonischen
  Registry. Ein Drift zwischen Research und App blockiert die Verifikation.

## Bewusst nicht aktiviert

- EDINET erst nach einem realen Japan-Fall.
- OpenDART erst nach einem realen Korea-Fall.
- FRED erst nach fachlicher Zuordnung konkreter Makro-Claims.
- Tiingo EOD erst nach Daten-, Rechte- und Kostenfreigabe.
- EODHD nur als Reserve nach einer belegten geografischen Datenlücke.
- TradingView bleibt ein manueller Plausibilitätscheck, keine Backend-Quelle.
- Kein Zeitplaner und keine automatische Marktüberwachung vor Abschluss der
  menschlichen Kernanalyse-Prüfung.

## Menschliche P5-Gates

Die Technik ist bereit für die Verifikation, aber nicht für eine autonome
Massenproduktion. Als Nächstes werden ein echter 100-Titel-Plan, ein bestätigter
Nullkosten-Lauf, Wiederaufnahme/Fehlerledger und eine erzeugte Change-Review-Aufgabe
vom Operator geprüft. Erst danach kann über 1.000 Titel oder neue Länderadapter
entschieden werden.
