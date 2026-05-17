# Pilot-v1 Baseline

- Batch-ID: `phase12_current_batch_001`
- Price Basis Date: `2026-05-08`
- Passed: `9`
- Manual review: `3`
- Failed: `0`
- Avg quality: `88.75`

## External Display Policy

Wenn `status = manual_review` und der Reason/Audit-Code `MISSING_FCF_SUPPORT_FOR_ACCUMULATE` enthält, wird extern nicht einfach `Accumulate` angezeigt.

Externe Anzeige:

`Manual Review / Hold Pending FCF Support / Accumulate only after FCF support`

## Template Status

- Gold-v1 Templates: `GOOGL`, `SNOW`
- Near-Gold Templates: `MSFT`
- Gute interne Drafts: `AAPL`, `META`, `NFLX`, `AVGO`, `DDOG`, `CRM`
- Manual Review: `MU`, `NVDA`, `QCOM`

## Bekannte Grenzen

- Nicht unbeaufsichtigt veröffentlichen.
- `manual_review` ernst nehmen.
- Passed Reports stichprobenartig prüfen.
- Outcome Backtesting erst vollständig bewerten, wenn `5D`-, `10D`-, `20D`- und `60D`-Fenster gereift sind.

## Empfohlener Betrieb

- Fresh Batch laufen lassen.
- Dashboard prüfen.
- `manual_review` immer prüfen.
- Wichtige Echtgeld-Reports extern reviewen.
- Outcome nach `5D`, `10D`, `20D` und `60D` auswerten.
