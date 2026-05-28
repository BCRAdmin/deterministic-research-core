# OpenJarvis Component Adapter

## Zweck

Der Component Adapter macht aus OpenJarvis ein Teilelager: gute Muster werden
identifiziert, bewertet und als eigene Vega-/PIG-/LIONCOM-Bausteine
nachgebaut oder gehärtet. Die Bewertung läuft über Komponenten statt über die
Frage, ob OpenJarvis als Gesamtsystem übernommen wird.

## Dauerhafte Bausteine

- `github_dependabot_digest`: read-only Repo-/PR-/Dependabot-Digest mit `gh`.
- `tool_surface_audit`: Tool-Inventar und Deny-by-default-Policy für gefährliche
  Fähigkeiten wie Shell, Writes, Git-Commit und HTTP.
- `skill_mining`: externe Skills nur lesen, klassifizieren und als lokale Skills
  neu schreiben.
- `retrieval_shadow`: bessere Retrieval-Ideen gegen PIG/Obsidian messen.
- `runtime_sandbox_protocol`: echte Runtime nur in isolierter Sandbox.
- `write_fix_worker`: aktuell abgelehnt, bis ein Wrapper mit Zeitlimit, Diff- und
  Testpflicht im Wegwerf-Repo besser abschneidet.

## Standardbefehl

```bash
python3 scripts/ops/openjarvis_component_adapter.py
```

Optionaler read-only GitHub-Digest:

```bash
python3 scripts/ops/openjarvis_component_adapter.py --run-github-digest
```

Der Digest darf nur Repo-/PR-Metadaten lesen. Kommentare, Labels, Branches,
Commits, Merges, Pushes und Releases bleiben verboten.

## Outputs

- `OPENJARVIS_COMPONENT_ADAPTER.json`
- `OPENJARVIS_COMPONENT_ADAPTER.md`
- `OPENJARVIS_COMPONENT_MATRIX.json`
- `OPENJARVIS_COMPONENT_ADAPTER_VALIDATION.txt`

## Einbau-Regel

Wenn ein OpenJarvis-Muster nützlich ist, wird es bevorzugt als kleiner lokaler
Baustein nachgebaut. OpenJarvis selbst bleibt Runtime-Testobjekt und
Inspiration, nicht die führende Betriebsschicht.
