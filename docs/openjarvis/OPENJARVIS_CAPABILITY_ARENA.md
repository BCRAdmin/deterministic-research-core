# OpenJarvis Capability Arena

## Zweck

Die Capability Arena testet OpenJarvis nicht als Runtime, sondern als Vergleichsschicht. Sie beantwortet: Bringt ein OpenJarvis-artiger Shadow-Index gegenüber PIG/Obsidian messbar bessere Quellenfindung, Gate-Erkennung oder Code-QA-Handoff-Vorbereitung?

## Engines

- `pig_obsidian_baseline`: nutzt nur `vega_backbone` und `pig_surface`.
- `openjarvis_shadow`: nutzt alle laut Policy erlaubten Shadow-Quellen.

## Scoring

Jede Aufgabe bewertet:

- erwartete Quellenmuster
- erwartete Pflichtbegriffe
- Operator-Gate-Begriffe
- verbotene stale oder unsafe Begriffe
- Evidence-Tiefe

## Harte Grenzen

- keine OpenJarvis-Runtime-Ausführung
- keine Shell
- keine Writes durch OpenJarvis
- kein Netzwerk
- keine GitHub-API
- kein PAT/OAuth
- kein Commit, Push, Release oder Public-/Production-Schritt

## Führender Befehl

```bash
python3 scripts/ops/openjarvis_capability_arena.py
```

Der Lauf schreibt:

- `outputs/openjarvis_capability_lab/capability_arena/CAPABILITY_ARENA_SCOREBOARD.json`
- `outputs/openjarvis_capability_lab/capability_arena/CAPABILITY_ARENA_SCOREBOARD.md`
- `outputs/openjarvis_capability_lab/capability_arena/CAPABILITY_ARENA_PREFLIGHT.json`
- `outputs/openjarvis_capability_lab/capability_arena/CAPABILITY_ARENA_TASK_RESULTS.jsonl`
- `outputs/openjarvis_capability_lab/capability_arena/CAPABILITY_ARENA_FILE_LIST.txt`
