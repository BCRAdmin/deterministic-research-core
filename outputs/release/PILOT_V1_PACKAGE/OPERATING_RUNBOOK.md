# OPERATING_RUNBOOK

## Wie Fresh Batch gestartet wird

`python -m research_agent.batch.batch_runner --config /Users/BjornRosinger/Documents/New project 2/outputs/batches/phase12_current_batch_003_config.json`

## Wie Dashboard gelesen wird

Auf `status`, `quality_score`, `external_display_rating`, `manual_review_reasons`, `true_source_disagreements`, `evidence_warnings` und `reconciliation_warnings` pro Ticker schauen.

## Was passed bedeutet

Passed bedeutet: kein Blocking-Audit, publishable Quality Gate, harte Claims voll evidence-gemappt und keine manuelle Stop-Regel aktiv.

## Was manual_review bedeutet

Manual Review ist ein echter Review-Stop. Der Report darf nicht als quasi-passed behandelt oder still extern weitergereicht werden.

## Wann man Reports extern reviewen lassen muss

- Immer vor externer Publikation.
- Immer bei True-Anomaly, Reconciliation-Noise oder FCF-/Current-Period-Sonderfaellen.

## Wie Outcome Backtesting spaeter laeuft

1D kann frueh geprueft werden. 5D/10D/20D/60D erst werten, wenn die Preisfenster vollstaendig sind.

## Welche Fehler nicht automatisch gefixt werden sollen

- True-Anomalien
- period_bug / Reconciliation-Brueche
- fehlender FCF-Support fuer offensivere Ratings
- fehlende Current-Period-Kontexte, die neue echte Daten verlangen

Operating Pilot baseline: `/Users/BjornRosinger/Documents/New project 2/outputs/batches/phase12_operating_pilot_050`
