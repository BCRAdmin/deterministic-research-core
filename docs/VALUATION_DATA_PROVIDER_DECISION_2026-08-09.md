# Room16: Entscheidungsvorlage für Total-Return-Daten

Stand: 9. August 2026

## Ergebnis

Für den ersten verifizierten US-/ETF-Kalibrationspfad ist **Tiingo EOD** der
bevorzugte Kandidat. Der Adapter ist lokal vorbereitet, aber vollständig
deaktiviert: Es wurde kein Konto eröffnet, kein Tarif gekauft, kein Token
gespeichert und kein aktiver Room16-Datenweg umgestellt.

Die Entscheidung ist keine rechtliche Freigabe. Vor einem echten Lauf müssen
Tarif, Nutzungsumfang und Evidence vom Operator bestätigt werden.

## Warum Tiingo zuerst

- Die offizielle EOD-Dokumentation weist Roh- und bereinigte OHLCV-Werte,
  `divCash` und `splitFactor` gemeinsam aus.
- Tiingo beschreibt die bereinigten Preise ausdrücklich als split- und
  dividendenbereinigt nach der Methodik des Center for Research in Security
  Prices (CRSP).
- Aktien und ETFs laufen über denselben dokumentierten EOD-Endpunkt. Damit
  können MCD und ein ETF-Benchmark wie SPY auf derselben Anbieter- und
  Methodikbasis geprüft werden.
- Der Business-Tarif für interne kommerzielle Nutzung ist transparent mit
  `50 USD/Monat` beziehungsweise `499 USD/Jahr` ausgewiesen.
- Für Display-/Redistribution nennt Tiingo einen Start-up-Tarif von
  `250 USD/Monat`. Ob ausschließlich abgeleitete Kennzahlen in kostenlosen
  oder bezahlten Room16-Berichten bereits darunter fallen, muss Tiingo
  schriftlich bestätigen; Room16 nimmt dies nicht selbst an.

Offizielle Nachweise:

- [Tiingo EOD-Dokumentation](https://www.tiingo.com/documentation/end-of-day)
- [Tiingo EOD-Produkt und Preise](https://www.tiingo.com/products/end-of-day-stock-price-data)
- [Tiingo allgemeine Nutzungshinweise](https://www.tiingo.com/documentation/general)
- [Tiingo Preise](https://www.tiingo.com/about/pricing)

## Vergleich der realistischen Kandidaten

| Kandidat | Total-Return-Semantik | Interne kommerzielle Nutzung | Veröffentlichung | Room16-Entscheidung |
| --- | --- | --- | --- | --- |
| Tiingo EOD | Bereinigte Preise umfassen Splits und Dividenden; CRSP-Methode dokumentiert | `50 USD/Monat` | Start-up-Redistribution ab `250 USD/Monat`; abgeleitete Reports schriftlich klären | Bevorzugter erster US-/ETF-Pilot |
| EODHD EOD All World | `adjusted_close` wird als split- und dividendenbereinigt beschrieben | Persönlicher Einstieg `19,99 USD/Monat`; separate B2B-Seite nennt `399 USD/Monat` für Internal Use | Externe Weitergabe ist im Internal-Use-Paket ausgeschlossen; Custom-Vertrag nötig | Globale Reserve, für den ersten Pilot deutlich teurer und vertraglich komplexer |
| Massive Stocks | Aggregate standardmäßig split-, aber ausdrücklich nicht dividendenbereinigt; Dividenden separat | Stocks Business `1.999 USD/Monat` | Business-/Redistribution-Vertrag erforderlich | Für Room16-Total-Return unnötig teuer und methodisch zusätzlicher Eigenbau |
| Alpha Vantage | Adjusted Daily umfasst laut Anbieter Splits und Cash-Dividenden | Kommerzielle Nutzung nur nach Kontakt; kein transparenter Businesspreis | Schriftliche kommerzielle Vereinbarung erforderlich | Methodisch brauchbar, wirtschaftlich vorab unklar |
| Twelve Data | Tagespreise splitbereinigt; Dividenden separat verfügbar | Individualtarife sind nichtkommerziell; Dividenden im Business-Venture-Tarif | Business-/Redistribution-Klärung erforderlich | Für den ersten Pilot unnötig komplex und preislich unklar |

Weitere offizielle Nachweise:

- [EODHD Preise](https://eodhd.com/pricing)
- [EODHD kommerzielle Preise](https://eodhd.com/commercial-pricing)
- [EODHD Adjusted-Close-Beschreibung](https://eodhd.com/lp/historical-eod-api)
- [EODHD Nutzungsbedingungen](https://eodhd.com/financial-apis/terms-conditions)
- [Massive Business-Preise](https://massive.com/business)
- [Massive Split-/Dividendenadjustierung](https://massive.com/knowledge-base/article/is-massives-stock-data-adjusted-for-splits-or-dividends)
- [Alpha Vantage Adjustierungsmethodik](https://www.alphavantage.co/support/)
- [Alpha Vantage Nutzungsbedingungen](https://www.alphavantage.co/terms_of_service/)
- [Twelve Data Preisadjustierung](https://support.twelvedata.com/en/articles/5179064-are-the-prices-adjusted)
- [Twelve Data Dividenden-API](https://twelvedata.com/docs/introduction/overview)
- [Twelve Data Preise](https://twelvedata.com/pricing)

## Warum EODHD und Massive nicht gewinnen

Die ursprünglich notierte Annahme eines kommerziellen EODHD-Tarifs für
`19,99 USD/Monat` war falsch. Dieser Preis gehört zum persönlichen
Self-Service-Einstieg. Die separate offizielle B2B-Seite nennt für interne
Firmennutzung `399 USD/Monat`. Sie nennt direkte Verträge mit über 60 Börsen,
während der Disclaimer derselben Seite zugleich von über 100 aggregierten
OTC-, Peer-to-Peer- und Plattformquellen spricht. Diese Provenienzabgrenzung
müsste vor Golden-Standard-Nutzung geklärt werden. Zusätzlich verlangen die
Bedingungen bei Vertragsende die Löschung gespeicherter Daten innerhalb eines
Monats; externe Weitergabe ist im Internal-Use-Paket ausgeschlossen.

Massive ist für US-Marktdaten stark, liefert historische Aggregate aber laut
eigener FAQ nur split- und nicht dividendenbereinigt. Room16 müsste deshalb
Dividenden und Adjustment-Faktoren selbst zu einer Total-Return-Reihe
zusammenbauen und dauerhaft gegen Corporate-Action-Korrekturen testen. Der
offizielle Business-Tarif beginnt zugleich bei `1.999 USD/Monat`.

EODHD bleibt wegen seiner Weltmarktabdeckung ein späterer Kandidat. Für den
ersten MCD-/SPY-Golden-Standard-Fall bietet Tiingo jedoch die direkteste
Methodik, den kleinsten Eigenbau und mit `50 USD/Monat` den niedrigsten klar
ausgewiesenen internen Geschäftstarif dieser drei Kandidaten.

## Vorbereiteter technischer Zustand

Der deaktivierte Adapter liegt unter:

```text
research_agent/sources/prices/tiingo_total_return_provider.py
```

Er:

- liest ausschließlich Tiingos dokumentierten EOD-Endpunkt;
- überträgt das Token nur im `Authorization`-Header, nie in URL oder Log;
- normalisiert Roh- und Adjusted-OHLCV sowie Dividende und Splitfaktor;
- lehnt ungültige Symbole, Zeiträume, Dubletten, nicht endliche Werte,
  nichtpositive Preise und widersprüchliche OHLC-Zeilen ab;
- erzeugt für die Outcome-Workbench ausschließlich `date` plus
  `adjusted_close` als Total-Return-Kandidatenreihe; und
- bleibt ohne `TIINGO_API_TOKEN` fail-closed deaktiviert.

Die Metadaten sagen ausdrücklich
`operator_purchase_and_rights_evidence_required`. Ein vorhandener Token würde
deshalb noch keine Rechtefreigabe, menschliche Prüfung oder Live-Aktivierung
erzeugen.

Ein späterer echter Probeabruf ist zusätzlich kosten- und dirt-geschützt:

```bash
python -m research_agent.sources.prices.tiingo_total_return_provider \
  --ticker MCD \
  --start 2025-07-31 \
  --end 2026-08-07 \
  --output-dir <BESTEHENDER_RUNTIME_PFAD>/MCD-candidate \
  --confirm-paid-provider
```

Ohne das ausdrückliche Flag oder ohne `TIINGO_API_TOKEN` findet kein Abruf
statt. Der Elternpfad muss bereits existieren und ein vorhandenes Ziel wird
nicht überschrieben. Ein erfolgreicher Lauf legt atomar genau einen neuen
Kandidatenordner mit `prices.csv` und `provider_receipt.json` an. Der Beleg
bindet Abfragezeitraum, Anbieter, Methodik, Zeilenumfang und Datei-Hash, enthält
aber weder Token noch eine behauptete Rechtefreigabe. Auch ein erfolgreicher
Download bleibt `operator_evidence_still_required` und
`live_activation_allowed=false`.

Der Providerbeleg ist inzwischen verbindlich an die v2-Outcome-Workbench
angeschlossen. Ein verifizierter Lauf benötigt getrennte Belege für Instrument
und Benchmark. Die Workbench prüft jeweils CSV-Hash, Zeilen und Zeitraum sowie
Ticker, Anbieter, Datensatz und Total-Return-Eigenschaften. Beide Belege müssen
denselben Provenienzvertrag ausweisen; `retrieved_at` muss exakt dem späteren
Belegzeitpunkt entsprechen. Die Belege werden gemeinsam mit ihren Kursdateien
in das selbstständige Evidence-Paket kopiert und erneut validiert. Manuell
eingetragene Providerbehauptungen reichen damit nicht mehr aus.

## Schriftlich zu klärende Punkte

Vor dem Kauf sollte Tiingo folgende Verwendung schriftlich einordnen:

1. BCR Ventures UG nutzt EOD-Daten intern zur Erstellung und Prüfung eigener
   Unternehmensanalysen.
2. Rohdaten, Tabellenzeilen und herunterladbare Kursreihen werden nicht an
   Leser weitergegeben.
3. Ausgewählte Berichte können später kostenlos oder bezahlt veröffentlicht
   werden und enthalten nur selbst berechnete Renditen, Bewertungskennzahlen,
   Szenarien und redaktionelle Einordnung.
4. Es muss bestätigt werden, ob diese abgeleiteten Werte bereits eine
   Redistribution-Lizenz benötigen.
5. Es muss geklärt werden, ob ein unabhängiger menschlicher Prüfer einzelne
   Evidence-Auszüge innerhalb der Organisation beziehungsweise als
   beauftragter Prüfer einsehen darf.
6. Aufbewahrungs- und Löschpflichten nach einer Kündigung müssen feststehen.

## Vorbereitete Anfrage an Tiingo

**Empfänger:** `sales@tiingo.com`

**Betreff:** Commercial internal use and derived research reports

> Hello Tiingo team,
>
> BCR Ventures UG is a German start-up with fewer than five employees. We are
> evaluating Tiingo EOD data for an internal equity-research system. We would
> use adjusted EOD prices, dividends and split factors for internal
> calculations and methodology validation.
>
> We would not expose or redistribute raw Tiingo rows, downloadable price
> series or API access. In a later stage, selected free or paid research reports
> may contain only our derived returns, valuation metrics, scenarios and
> editorial conclusions.
>
> Could you please confirm in writing:
>
> 1. whether the USD 50/month commercial internal-use plan covers this internal
>    calculation and validation workflow;
> 2. whether publishing only derived figures in free or paid PDF/web reports
>    requires your redistribution plan;
> 3. whether an independent contracted human reviewer may inspect limited
>    evidence extracts without receiving the underlying dataset; and
> 4. which retention or deletion obligations apply after cancellation?
>
> We will not activate the integration until the applicable license scope is
> confirmed.
>
> Kind regards
> BCR Ventures UG

Die Anfrage wurde nur vorbereitet und nicht versendet.

## Kostenarchitektur

1. **Jetzt ohne Kauf:** Adapter, Vertragsprüfung und Fixtures bleiben lokal;
   Bewertung bleibt unkalibriert und neutral.
2. **Interner Pilot nach Operator-Go:** voraussichtlich `50 USD/Monat` für
   Tiingo Commercial Internal Use. Zuerst nur MCD und SPY verifizieren.
3. **Öffentliche Gratisberichte:** erst nach schriftlicher Antwort, ob
   abgeleitete Werte im internen Tarif zulässig sind. Kein automatisches
   Upgrade.
4. **Bezahlte Berichte oder sichtbare Daten:** falls Tiingo dies als
   Redistribution einordnet, separat ab `250 USD/Monat` bewerten.
5. **Internationale Erweiterung:** erst bei echtem Bedarf Tiingo-Abdeckung oder
   EODHD gegen den jeweiligen Länderadapter und dessen Rechte prüfen.

Damit bleibt Room16 weit unter Bloomberg-Kosten, ohne Datenrechte oder
Total-Return-Qualität wegzuerklären.
