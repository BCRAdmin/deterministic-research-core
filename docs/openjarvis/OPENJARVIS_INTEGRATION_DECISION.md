# OpenJarvis Integration Decision

## Entscheidung

OpenJarvis wird als gehärtetes Capability-Lab integriert, nicht als Control Plane.

## Live-Trial-Entscheidung 2026-05-25

Nach Operator-Go wurden die drei zuvor blockierten Trials sicher ausgeführt:

- Runtime-Sandbox: `PASS_WITH_WARNINGS`. OpenJarvis `1.0.1` ließ sich in einer isolierten Sandbox installieren; `jarvis --help`, `jarvis --version`, `jarvis doctor`, Preset-Init und ein minimaler Calculator-Ask liefen. Der `code-assistant`-Preset aktiviert aber standardmäßig `file_write`, `shell_exec`, `git_commit`, `http_request` und `web_search`; deshalb bleibt er für echte Repos gesperrt.
- GitHub-/Dependabot-Digest: `PASS`. Bestehendes `gh` reicht für einen read-only Digest über BCRAdmin-Repos und offene Dependabot-PRs. Dafür muss kein Jarvis-Connector übernommen werden.
- Write-/Fix-Sandbox: `FAIL_FOR_ADOPTION`. Im Wegwerf-Repo erzeugte OpenJarvis nach ca. zwei Minuten keinen Patch und keine Testverbesserung. Die Vega/Codex-Kontrollprobe löste denselben Bug mit kleinem Patch und grünen Tests.

Aktuelle Entscheidung: OpenJarvis nicht als isolierten Write-/Fix-Worker übernehmen. Nützlich bleiben die Muster für Runtime-Inventar, Tool-Surface-Audit und read-only Digest/QA-Handoffs.

## Warum

Dein bestehendes System ist führend bei Operator-Gates, Claims, PIG-Verifikation, LIONCOM-Surface, Vivi Worker und deterministischer Qualität. OpenJarvis kann trotzdem als Vergleichs- und Teilelager nützlich sein, besonders für Retrieval, Code-QA-Handoffs und Connector-Ideen.

## Gültige Übernahmeform

- `shadow_read_only` zuerst
- Runtime nur in expliziter Sandbox mit eigenem `HOME`, eigenem Workspace, Logs und Timeout-/Kill-Plan
- kein Schreibzugriff in echte Projekt-Repos
- kein Shell-Zugriff in echte Projekt-Repos
- GitHub nur read-only über bestehende Operator-Freigabe; keine Kommentare, Labels, Branches oder PR-Mutationen
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
- ein Write-/Fix-Trial im Wegwerf-Repo innerhalb eines festen Zeitlimits Patch, Diff und grüne Tests liefert.

## Abbruch-Kriterien

Abbruch bei Secret-Fund, Schreibversuch, Shell-/Netzwerkversuch, stale Memory ohne Warnung, falschem Truth-Claim oder Operator-Gate-Verletzung.
