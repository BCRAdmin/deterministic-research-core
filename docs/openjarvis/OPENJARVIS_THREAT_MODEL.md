# OpenJarvis Threat Model

## Hauptgefahren

1. Secret-Indexing aus `.env`, Tokens, Cookies oder lokalen Credentials.
2. Prompt-Injection aus Projektdateien.
3. Ungeprüfte Shell-Ausführung.
4. Ungeprüfte Dateiänderungen.
5. Jarvis-Memory wird fälschlich als Wahrheit behandelt.
6. GitHub-Connector schreibt Kommentare, Labels oder PRs ohne Operator-Go.
7. Stale Memory erzeugt falschen Projektstatus.

## Gegenmaßnahmen

- deny-globs für Secrets, Runtime-Ordner, `.git`, `node_modules`, `.venv`, Report-Runs und Debug-Bundles
- Secret-Regex vor jedem Benchmark
- `runtime_execution_allowed=false`
- `allow_shell=false`
- `allow_write=false`
- `allow_network=false`
- `allow_github_api=false`
- maschinenlesbare Reports mit `runtime_action_executed=false`
- PIG/LIONCOM nur als Anzeige und Gate, nicht als Jarvis-Autostart

## Operator-Gates

Diese Aktionen bleiben immer Operator-Gate:

- Runtime-Ausführung von OpenJarvis
- Installation externer Skills
- GitHub-API mit Token
- Writes in Projekt-Repos
- Shell-Kommandos durch Jarvis
- Commit, Push, Merge, Release, Public, Production, Payment oder Credentials
