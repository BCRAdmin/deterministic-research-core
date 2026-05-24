# OpenJarvis Capability Lab

## Zweck

OpenJarvis wird nicht als Ersatz für LIONCOM, Vivi, Vega, PIG oder das Obsidian-Backbone eingebaut. Diese Spur prüft OpenJarvis nur als externen Capability-Provider für Retrieval, Code-QA-Handoffs und spätere GitHub-Digests.

## Führende Regel

OpenJarvis ist niemals `source_of_truth`. Wahrheit bleibt bei PIG, Obsidian, repo-lokalen Verträgen und deterministischen Verifiern.

## Betriebsmodus

- Modus: `shadow_read_only`
- Shell: aus
- Writes: aus
- Netzwerk: aus
- GitHub API: aus
- Runtime-Ausführung: aus
- Secret-Scan: Pflicht vor jedem Index
- Operator-Go: Pflicht vor jeder späteren Runtime-Aktivierung

## Zielnutzen

1. Retrieval-Benchmark gegen PIG/Obsidian.
2. Read-only QA-Handoff für Repos mit vorhandenen Checks.
3. Später optional GitHub-/Dependabot-Digest, zuerst ohne Jarvis-PAT.

## Nicht-Ziele

- kein Umbau auf OpenJarvis
- kein Ersatz für Vivi Worker
- keine zentrale Jarvis-Memory-Wahrheit
- keine direkten Codeänderungen durch Jarvis
- kein Commit, Push, Release, Public-/Production- oder Geld-Schritt

## Verifier

Führender lokaler Befehl:

```bash
python3 scripts/ops/openjarvis_capability_lab.py
```

Der Lauf schreibt:

- `outputs/openjarvis_capability_lab/OPENJARVIS_CAPABILITY_LAB.json`
- `outputs/openjarvis_capability_lab/OPENJARVIS_CAPABILITY_LAB.md`
- `outputs/openjarvis_capability_lab/OPENJARVIS_PREFLIGHT.json`
- `outputs/openjarvis_capability_lab/OPENJARVIS_BENCHMARK.json`
- `outputs/openjarvis_capability_lab/OPENJARVIS_FILE_LIST.txt`
