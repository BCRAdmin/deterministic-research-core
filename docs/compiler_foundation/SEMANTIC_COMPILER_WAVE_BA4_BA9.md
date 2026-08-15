# Semantic Compiler Wave BA4–BA9

Status: **IMPLEMENTED IN SHADOW MODE**. BA10 ist nicht autorisiert.

Die Welle arbeitet ausschließlich oberhalb der eingefrorenen Compiler
Foundation 1.0.0 und Registry Foundation 1.1.0. Sie liest die akzeptierten
Authority-Bundle-v3-Artefakte von WM, COST und ABT als unveränderliche
Shadow-Inputs. Sie ersetzt noch keinen produktiven Legacy-Ausgabepfad.

## BA4 — Parser + Table Discovery

JSON-, CSV- und Textartefakte werden hashverifiziert geparst. Tabellen erhalten
stabile IDs, explizite Zero/Missing/Not-applicable-Zustände und Zell-Locators.
Bereits akzeptierte v3-Tabellenlineage wird für Shadow-Parität als klar
gekennzeichnete Legacy-Bridge übernommen. Beschädigte Payloads und Parserfehler
blockieren fail closed.

## BA5 — Typed Fact IR

Legacy-Facts werden deterministisch normalisiert, gegen die Registry gebunden
und in TypedFactIR überführt. Dimension, Einheit, Währung, Periode, Wertzustand,
Source- und Evidence-Lineage bleiben explizit. Formeloperanden werden als interne
Operand-Facts materialisiert; unbekannte Metrics, Zustandskollisionen und
widersprüchliche Fact-IDs blockieren.

## BA6 — Metric + Formula Engine

Metric-Instanzen referenzieren generische Definitionen. Jede echte
Formula-Instanz besitzt registrierte Operandrollen, Operand-Fact-IDs,
Ergebnisdimension, Rundungsregel und Reproduktionshash. Der Compiler rechnet alle
Legacy-Formeln erneut und vergleicht binär64-nah mit dem akzeptierten Ergebnis.
Reine Legacy-Parametermarker bleiben `diagnostic_only` und werden nicht als
Berechnung ausgegeben.

## BA7 — Evidence Graph

Sources, Evidence Items und Typed Facts werden über stabile Nodes und Edges
verbunden. Ein Fact ohne vorhandenen Evidence-Pfad bleibt sichtbar als Orphan und
blockiert das Release-Gate. Es wird keine fehlende Evidenz erfunden.

## BA8 — Claim Graph

Jeder Claim benötigt einen registrierten Claim Kind, bekannte Evidence-IDs und
gültige Fact-Bindings. Unbekannte Kinds, unbekannte Belege und unbekannte Facts
werden getrennt diagnostiziert und blockieren. Claim-Text wird nicht neu
generiert.

## BA9 — Decision Graph

Das komplette Legacy-Decision-Packet wird lossless in DecisionGraphIR gebunden.
Decision Inputs, Risk Definition und Permission Corridor stammen aus der
Research Registry. Rating Corridor, Publication Permission und Non-advice-
Boundary sind verpflichtend. Der Roundtrip zurück zum Legacy-Payload muss exakt
denselben kanonischen Hash liefern.

## Gemeinsame Gates

- gleiche Pass-, Registry-, Schema- und Engine-Version für WM, COST und ABT;
- zweimal identischer Replay-Hash je Unternehmen;
- unveränderte Canary-ZIP-Hashes;
- 100 Prozent Registry-Coverage, null ausführbare Unknowns, null Kollisionen;
- alle Formeln reproduziert, null Evidence-Orphans, vollständige Claim-Bindung;
- lossless Decision-Roundtrip;
- Product-Mirror hashidentisch und ohne Parallelwahrheit;
- Foundation 1.0.0 und Authority Bundle v3 unverändert;
- alle Negativfixtures scheitern defekt, bestehen korrigiert und blockieren bei
  erneuter Einführung.

Diese Welle validiert die semantische Compilerstrecke. Renderer, Emission,
produktiver Cutover und BA10 bleiben außerhalb des genehmigten Scopes.
