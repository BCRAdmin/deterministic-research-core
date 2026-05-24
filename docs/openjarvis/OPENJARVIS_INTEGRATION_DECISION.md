# OpenJarvis Integration Decision

## Entscheidung

OpenJarvis wird als gehärtetes Capability-Lab integriert, nicht als Control Plane.

## Warum

Dein bestehendes System ist führend bei Operator-Gates, Claims, PIG-Verifikation, LIONCOM-Surface, Vivi Worker und deterministischer Qualität. OpenJarvis kann trotzdem als Vergleichs- und Teilelager nützlich sein, besonders für Retrieval, Code-QA-Handoffs und Connector-Ideen.

## Gültige Übernahmeform

- `shadow_read_only` zuerst
- keine Runtime-Ausführung
- kein Schreibzugriff
- kein Shell-Zugriff
- keine GitHub-API
- keine Secrets im Index
- Ergebnisse nur als Evidence, nie als Wahrheit

## Adoption-Kriterien

OpenJarvis-Funktionen dürfen erst weiter übernommen werden, wenn:

- der Retrieval-Benchmark Quellen korrekt nennt,
- Operator-Gates erkannt werden,
- keine Secrets indexiert werden,
- keine ungeplanten Dateien entstehen,
- keine mutierenden Aktionen ausgeführt werden,
- ein bestehender Workflow messbar besser wird.

## Abbruch-Kriterien

Abbruch bei Secret-Fund, Schreibversuch, Shell-/Netzwerkversuch, stale Memory ohne Warnung, falschem Truth-Claim oder Operator-Gate-Verletzung.
