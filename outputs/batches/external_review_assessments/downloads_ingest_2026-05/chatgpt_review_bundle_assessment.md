# ChatGPT Review — `chatgpt_review_bundle.zip`

## Kurzurteil

Das Bundle zeigt, dass der technische Kontroll-Backbone stabil läuft, aber die fünf `final_report.md`-Dateien sind noch keine echten Aktien-Research-Reports. Sie sind eher Validierungs-/Packet-Summaries: Datenbasis, Kennzahlentabelle, Validation-Status, Rating-Permission und Source Quality. In allen fünf Reports steht explizit: **"No LLM claims attached. Use validated packets before adding interpretation."**

Deshalb ist das aktuelle System **technisch pilotfähig**, aber die finalen Reports sind **inhaltlich nicht publishable**. Die Quality Scores messen derzeit überwiegend technische Sauberkeit, nicht Research-Vollständigkeit.

## Wichtigste Findings

### 1. Quality Score ist zu optimistisch

Die Scores 95–99 wirken sehr gut, aber sie sind für diese Reports irreführend, weil die Reports fast keine Analysteninterpretation enthalten. Ein Report ohne Investment-These, ohne Segmentanalyse, ohne Risikoabschnitt und ohne Szenarien darf nicht `Writing/Structure = 10` und `Publishable = true` bekommen.

**Empfohlene neue Regel:** Wenn `analyst_claim_count == 0` oder der Text `No LLM claims attached` enthält, dann:

- `publishable = false`
- Status: `technical_pass_research_incomplete`
- Content Completeness Score maximal 40/100

### 2. Evidence Report ist für menschliche Prüfung zu schwach

In allen Evidence Reports stehen harte Kennzahlen wie `revenue_ttm`, `free_cash_flow_ttm` und `sbc_to_revenue` mit `Value = n/a`. Das ist für einen Review nicht ausreichend. Evidence muss nicht nur sagen, dass eine Quelle existiert, sondern auch:

- Wert
- Periode
- Basis: GAAP / Non-GAAP / company-defined / consensus
- Evidence ID
- Quelle
- ggf. Source line oder Source excerpt

### 3. Reconciliation Report ist zu lang und nicht review-freundlich

Der Reconciliation Report listet historische Canonical Metrics über viele Jahre. Für Maschinen ist das okay, für menschliche Review nicht. Es braucht zusätzlich eine kurze `current_period_reconciliation_summary.md` mit nur:

- aktuelle TTM/FY/Q-Kennzahlen
- echte unresolved disagreements
- ignorierte frame variants als Summary
- finale Canonical Metrics, die ins MetricsPacket gingen

### 4. Es gibt harte Metrik-Anomalien trotz grüner Pipeline

Die größten roten Flags:

- AMZN: `FCF TTM = 104.495B` im Report, während Amazon offiziell für TTM bis 31.03.2026 nur ca. `1.2B` Free Cash Flow meldete.
- NVDA: `FCF TTM = 60.496B`, `SBC / Revenue = 38.8%`, `EV/Sales = 435.86`. Offizielle NVIDIA-Zahlen zeigen FY2026 FCF von `96.575B`, FY2026 Umsatz von `215.938B` und SBC von `6.386B`, was eine SBC/Revenue-Quote von ca. 3% nahelegt, nicht 38.8%.
- AMZN und NVDA sollten daher im source_ingestion_mode nicht `publishable` sein, solange diese Metriken nicht reconciled sind.

### 5. Die finalen Ratings sind mechanisch, nicht research-basiert

AMZN `Accumulate`, DDOG `Hold`, INTU `Hold`, NVDA `Hold`, SNOW `Tactical Underweight` können als Decision-Permission-Ergebnis okay sein. Aber ohne Analyst Claims, Segmentlogik, Bewertungsthese und Risikoanalyse sind das **Rating-Korridore**, keine Investment-Entscheidungen.

## Ticker Review

### AMZN

**Bundle-Rating:** Accumulate
**Bundle-Quality:** 98
**Mein Urteil:** Nicht publishable. Metrikfehler blockierend.

Der Report meldet `FCF TTM = 104.495B`. Das sieht stark nach Verwechslung mit Cash/Cash-equivalents/restricted cash aus. Amazon meldete in der Q1-2026-Veröffentlichung TTM Operating Cash Flow von `148.5B`, aber Free Cash Flow von nur `1.2B`, getrieben durch stark erhöhte PPE-Investitionen. Damit ist das Accumulate-Rating auf dieser Datenbasis nicht belastbar.

**Fix:** FCF muss company-defined aus Amazon IR/Earnings Release priorisieren, nicht nur SEC raw facts. Danach Decision Engine erneut laufen lassen.

### NVDA

**Bundle-Rating:** Hold
**Bundle-Quality:** 97
**Mein Urteil:** Nicht publishable. Mehrere Metrik-Sanity-Fails.

NVIDIA meldete FY2026 Umsatz von `215.938B`, Operating Income von `130.387B`, Net Income von `120.067B`, Operating Cash Flow von `102.718B` und Free Cash Flow von `96.575B`. Der Report zeigt `FCF TTM = 60.496B`, was eher in die Nähe des Vorjahreswertes fällt. Gleichzeitig zeigt er `SBC / Revenue = 38.8%`; offiziell lag stock-based compensation FY2026 bei `6.386B`, also grob 3% des Umsatzes. `EV/Sales = 435.86` ist ebenfalls ein klares Einheiten- oder Denominatorproblem.

**Fix:** Für NVDA müssen FCF, Revenue, SBC und EV/Sales als blockierende Sanity-Checks behandelt werden. Der Report darf erst publishable werden, wenn diese Werte korrekt sind.

### DDOG

**Bundle-Rating:** Hold
**Bundle-Quality:** 99
**Mein Urteil:** Technisch sauberer Skeleton, aber kein Research Report.

DDOG hat im Bundle keine offensichtlichen extremen Ratio-Ausreißer wie NVDA/AMZN. Datadog selbst meldete für FY2025 Free Cash Flow von `914.717M` und eine FCF-Marge von 27%. Der Bundle-Wert `784.065M` kann je nach TTM-Fenster abweichen, muss aber im Evidence Report mit Periode und Definition offengelegt werden.

**Fix:** Evidence Report muss Wert/Periode anzeigen. Der finale Report braucht echte Interpretation: Wachstum, FCF-Qualität, SBC, Bewertung, technische Lage, Q1/Earnings-Risiko.

### INTU

**Bundle-Rating:** Hold
**Bundle-Quality:** 95
**Mein Urteil:** Nicht ausreichend prüfbar; hohe Reconciliation-Disagreements und auffällige SBC/Revenue.

INTU hat im Bundle `SBC / Revenue = 34.9%`, `P/FCF = 103.65` und 45 true source disagreements. Das kann stimmen oder ein Perioden-/Denominatorproblem sein, ist aber zu auffällig, um ohne Detailprüfung publishable zu sein. Der Report selbst bietet keine These, warum Hold trotz Preis unter 200-SMA und hoher Bewertung plausibel ist.

**Fix:** INTU braucht einen aktuellen-periodischen reconciliation digest und eine Sanity-Regel für ungewöhnlich hohe SBC/Revenue bei profitablen Large-Cap-Softwarefirmen.

### SNOW

**Bundle-Rating:** Tactical Underweight
**Bundle-Quality:** 98
**Mein Urteil:** Mechanisch plausibel, aber noch kein publishable Research.

Snowflake meldete für FY2026 Product Revenue von `4.472B`, FY2026 Free Cash Flow von `1.120B` und Adjusted Free Cash Flow von `1.193B`. Der Bundle-Wert `FCF TTM = 1.154B` liegt grob in dieser Zone und wirkt plausibler als AMZN/NVDA. Tactical Underweight passt mechanisch zu schwachem technischem Trend und hoher SBC-Quote. Trotzdem fehlt die Investment-These: Produktwachstum, NRR, RPO, FCF-Qualität, SBC, Bewertung, Konkurrenz und AI-Data-Cloud-Narrativ.

**Fix:** Aus dem Skeleton einen echten Report bauen und nur dann publishable setzen.

## Konkrete Codex/Vega-Regeln

### Regel 1: Content Completeness Gate

Wenn `No LLM claims attached` im final_report steht oder `analyst_claim_count == 0`:

```text
publishable = false
status = technical_pass_research_incomplete
content_score <= 40
```

### Regel 2: Review Bundle erweitern

Das ChatGPT Review Bundle muss künftig enthalten:

```text
final_report.md
quality_score.json
decision_packet.json
audit_report.json
evidence_report.md
reconciliation_report.md
report_manifest.json
metrics_packet.json
canonical_financials.json
reconciliation_warnings.json
source_registry.json
data_packet.json
```

### Regel 3: Evidence Report mit Werten

Evidence Report darf keine `n/a`-Werte für harte Metriken zeigen. Pflichtfelder:

```text
metric
value
period
basis
source_type
evidence_id
confidence
```

### Regel 4: Financial Sanity Guard

Blockiere oder mindestens Manual Review, wenn:

```text
EV/Sales > 100
SBC/Revenue > 30% bei Mega-Cap oder non-SaaS
P/FCF > 100 ohne Erklärung
FCF_TTM weicht stark von company-defined IR FCF ab
market_cap / revenue erzeugt absurdes multiple
```

### Regel 5: Company-defined FCF priorisieren

Für Unternehmen, die FCF in der IR-Veröffentlichung definieren, muss `company_defined_fcf` Vorrang vor SEC-raw-derived FCF haben.

### Regel 6: Current Period Digest

Neben dem langen Reconciliation Report muss ein kurzer Digest erzeugt werden:

```text
current_period_reconciliation_summary.md
```

Inhalt:

- finale verwendete Kennzahlen
- Periode
- Basis
- Source
- echte unresolved disagreements
- ignored frame variant count

## Gesamturteil

**Kontrollsystem:** Stark und pilotfähig.
**Finale Reports im Bundle:** Noch nicht researchfähig.
**Hauptproblem:** Das System erzeugt aktuell technische Validierungs-Skeletons, keine vollständigen Investment-Reports. Außerdem sind AMZN und NVDA trotz grüner Scores mit harten Metrikfehlern durchgekommen.

**Empfehlung:** Kein weiterer Architektur-Ausbau. Erst diese Hardening-Regeln umsetzen, dann erneut 5 Reports bündeln und nochmals extern prüfen.
