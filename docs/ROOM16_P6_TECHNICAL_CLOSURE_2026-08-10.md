# Room16 P6 – technischer Abschluss

Stand: 10. August 2026

P6 ist technisch für menschliche Daten- und Methodenprüfung vorbereitet. Das
ist ausdrücklich kein Performancebeleg und keine Kalibrationsaktivierung.

## Technisch fertig

- Gereifte Bewertungs-Outcomes benötigen exakt 252 gemeinsame künftige
  Handelstage aus verifizierten Total-Return-Reihen für Instrument und
  Benchmark.
- Instrument- und Benchmark-Drawdown werden aus demselben 252-Tage-Pfad
  deterministisch berechnet. Fehlende oder unplausible Drawdowns schließen
  das Outcome aus.
- Die Mindeststichprobe bleibt 75 effektive Outcomes, 25 Emittenten, fünf
  Sektoren und höchstens drei effektive Beobachtungen je Emittent.
- Eine hashgebundene, unabhängig menschlich geprüfte Klassifikation erlaubt
  Stabilitätsvergleiche nach Sektor, Marktphase und Bewertungsregime.
- Richtungsbezogene False-Pass-/False-Block-Raten und die Differenz zwischen
  früher und später Stichprobenhälfte werden transparent definiert. Ihre
  Interpretation ist ausschließlich menschlich.
- Sharpe, Strategie-Drawdown und annualisierte Rendite existieren nur hinter
  einem separaten Portfolio-Strategievertrag mit mindestens 252
  Tagesbeobachtungen. Sie sind keine Einzelberichtskennzahlen und dürfen kein
  Rating ändern.
- Unabhängiger Methodenreview und Operator-Sign-off sind hashgebunden. Selbst
  ein vollständiges Gate installiert keine Aktivierung; dafür bleibt ein
  separater manueller Code-Promotionsschritt mit neuer Regression nötig.

## Aktueller ehrlicher Status

- Tiingo EOD bleibt `paused_no_cost`.
- Es gibt noch keine verifizierte reale Total-Return-Stichprobe von 75
  effektiven Outcomes.
- `live_activation_allowed` bleibt immer `false`.
- Keine Performanceaussage, kein kalibriertes Rating und kein Sharpe-Wert aus
  einem Einzelbericht sind freigegeben.

## Menschliche und zeitliche Gates

Benötigt werden verifizierte Kursreihen samt Rechte- und Methodiknachweisen,
unabhängige Klassifikation, 75 gereifte Beobachtungen über 25 Emittenten und
fünf Sektoren, Methodenreview und Operator-Sign-off. Prospektive 252-Tage-
Evidenz braucht ungefähr ein Handelsjahr; Coding kann diese Reifung nicht
ersetzen.
