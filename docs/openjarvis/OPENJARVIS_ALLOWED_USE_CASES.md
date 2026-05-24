# OpenJarvis Allowed Use Cases

## Erlaubt im Shadow-Modus

- lokale Dokumente nach Policy scannen
- Retrieval-Fragen gegen erlaubte Quellen benchmarken
- QA-Scripts aus `package.json` oder `pyproject.toml` erkennen
- Handoff-Berichte schreiben
- OpenJarvis-Runtime nur erkennen, nicht ausführen

## Nicht erlaubt ohne neues Operator-Go

- `shell_exec`
- `file_write`
- GitHub-API mit PAT
- OAuth oder Connector-Aktivierung
- Indexing von Secrets, Runtime-Artefakten oder Report-Runs
- Jarvis als zentrale Memory- oder Truth-Schicht
- automatische PR-Kommentare
- automatische Fixes

## Erste sinnvolle Tests

1. Retrieval-Benchmark gegen PIG/Obsidian.
2. Read-only QA-Handoff für `microtool-starter-kit` oder `materialbedarf-rechner.de`.
3. Read-only Dependabot-/PR-Digest erst nach separatem Auth-Gate.
