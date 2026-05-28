# Review: chatgpt_publish_review_bundle.zip

## Befund

Das hochgeladene Bundle ist **nicht** das erwartete große Template-Propagation-Bundle mit MSFT/META/AAPL/NFLX/DDOG/CRM.

Im `bundle_manifest.json` steht:

- `source_batch_id`: `phase12_real_pilot_037_main_body_narrative`
- `selected_tickers`: `GOOGL`, `SNOW`

Damit ist es erneut ein GOOGL/SNOW-Bundle, nicht der größere Propagation-Run.

## Enthaltene Reports

| Ticker | Status laut Bundle | Urteil |
|---|---|---|
| GOOGL | passed | Gold-Standard-v1 / brauchbarer interner Analysten-Draft |
| SNOW | passed | Gold-Standard-v1 / brauchbarer interner Analysten-Draft |

## Technische Prüfung

### Positiv

- `publish_report.md` existiert für beide.
- Haupttext ist frei von offensichtlicher interner Systemsprache.
- Keine Claim-IDs im Haupttext.
- Current-period KPIs stehen im Haupttext.
- Evidence IDs bleiben im Appendix.
- Ratings sind plausibel.
- `publish_mechanical_language_count = 0`.
- `publish_claim_id_main_body_count = 0`.

### GOOGL

Der Haupttext enthält die wichtigsten aktuellen KPIs:

- Q1 revenue: `$109.90B`
- Google Cloud revenue: `$20.00B`
- Cloud growth: `63.0%`
- Q1 operating margin: `36.1%`
- Q1 capex: `$35.67B`
- TTM FCF: `$64.43B`
- Other Income gain: `$37.70B`
- RSI: `81.33`

Das `Hold`-Rating ist plausibel: sehr starke operative Qualität, aber überhitzte Technik und AI-CapEx/FCF-Conversion-Debatte.

### SNOW

Der Haupttext enthält die wichtigsten aktuellen KPIs:

- Product revenue: `$4.47B`
- NRR: `125.0%`
- RPO: `$9.77B`
- Customers > $1M product revenue: `733`
- Adjusted FCF: `$1.19B`
- SBC/Revenue: `26.4%`
- Kurs unter 50-SMA und 200-SMA

Das `Tactical Underweight`-Rating ist plausibel: gute Unternehmensqualität, aber hohe SBC-Intensität und schwacher Chart.

## Was noch fehlt

Diese beiden Reports sind als interne Gold-Standard-v1-Templates brauchbar, aber noch nicht extern final.

Offene Punkte:

1. **Valuation/Sensitivity ist noch leicht.**
   - GOOGL hat EV/Sales und P/FCF, aber keine echte Sensitivity.
   - SNOW hat EV/Sales und P/FCF, aber keine modellartige Szenario-Spanne.

2. **Action Plans sind noch zu allgemein.**
   - GOOGL: „wait for technical reset or proof of AI FCF growth“ ist korrekt, aber Trigger könnten konkreter sein.
   - SNOW: „reclaim 50-SMA/200-SMA“ ist gut, aber konkrete Re-Entry-/Downgrade-Trigger könnten stärker sein.

3. **Evidence Appendix ist intern gut, extern zu dicht.**
   - Für interne Nutzung okay.
   - Für externe Veröffentlichung müsste der Appendix gekürzt oder in Fußnoten/Quellenanhang umgebaut werden.

## Wichtigster Hinweis

Der nächste gewünschte große Schritt war Template-Propagation auf:

- MSFT
- META
- AAPL
- NFLX
- DDOG
- CRM

Dieses Bundle enthält diese Reports nicht. Wenn Vega den Master-/Propagation-Prompt ausgeführt hat, wurde entweder das falsche ZIP hochgeladen oder Vega hat weiterhin nur GOOGL/SNOW in das Bundle gepackt.

## Nächster sinnvoller Auftrag an Vega

Bitte nicht erneut GOOGL/SNOW bündeln. Stattdessen prüfen, ob der Propagation-Run wirklich erzeugt wurde und das richtige Bundle exportieren.

Empfohlener kurzer Prompt:

```text
Prüfe, ob der Run phase12_real_pilot_039_template_propagation_plus_valuation oder der aktuelle Gold-Template-Propagation-Run existiert.

Das Bundle soll nicht nur GOOGL/SNOW enthalten, sondern alle passed Reports aus der Propagation-Kohorte.

Erwartete Ziel-Ticker, falls passed:
- MSFT
- META
- AAPL
- NFLX
- DDOG
- CRM
- plus GOOGL/SNOW als Gold-Kontrolle

Wenn nur GOOGL/SNOW enthalten sind:
- erkläre warum die anderen Ticker nicht passed sind
- gib pro nicht enthaltenem Ticker den manual_review-Grund aus
- erzeugt ein neues chatgpt_publish_review_bundle.zip mit allen passed Reports aus dem Propagation-Run
- kopiere dashboard_status.json und pilot_review.md dazu
```

## Gesamturteil

GOOGL und SNOW sind weiterhin brauchbare interne Gold-Standard-v1-Templates.

Aber das hochgeladene Bundle ist nicht der große Propagation-Nachweis. Es beantwortet noch nicht die Frage, ob der Stil auf MSFT/META/AAPL/NFLX/DDOG/CRM übertragen wurde.
