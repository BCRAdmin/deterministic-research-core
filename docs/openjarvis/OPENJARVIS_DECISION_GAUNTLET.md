# OpenJarvis Decision Gauntlet

## Zweck

Der Decision Gauntlet ist die finale Prüfschicht vor einer Jarvis-Entscheidung. Er beantwortet nicht nur, ob der Shadow-Test gut aussieht, sondern welche Arbeit und welche Tests vollständig erledigt sein müssen, bevor Jarvis als Baustein, Worker oder gar nicht übernommen wird.

## Führende Entscheidung

OpenJarvis wird nicht automatisch eingebaut. Es muss sich in vier Ebenen beweisen:

1. `shadow_read_only` Retrieval und Code-QA gegen PIG/Obsidian.
2. Operator-Surface-Sichtbarkeit in Agent Ops, PIG und LIONCOM.
3. Runtime-, GitHub- und Write-Sandbox-Trials nur nach separatem Operator-Go.
4. Klare ROI-Entscheidung: übernehmen, Bausteine nachbauen oder verwerfen.

## Testflächen

- Governance und Truth-Vertrag
- Source-, Secret- und Index-Hygiene
- Retrieval-/Memory-Qualität
- Arena-Entscheidungsqualität
- Code-QA Shadow
- PIG-/LIONCOM-Operator-Surface
- Runtime-Sandbox-Pilot
- GitHub-/Dependabot-Digest-Pilot
- Write-/Fix-Sandbox-Pilot
- ROI- und Exit-Kriterien
- Observability und Evidence-Pack
- Rollback-, Cleanup- und Commit-Grenzen

## Harte Grenzen

- Keine OpenJarvis-Runtime ohne Operator-Go.
- Keine Shell, Writes, Netzwerk oder GitHub-API ohne Operator-Go.
- Keine Secrets, Tokens, Cookies oder `.env` in den Index.
- Kein Commit, Push, Release, Public oder Production.
- Kein Ersatz für PIG, Obsidian, LIONCOM, Vivi/Vega oder deterministische Verifier.

## Entscheidungsausgänge

- `reject_or_keep_reference_only`: Jarvis bleibt Vergleichs- und Ideenquelle.
- `use_as_shadow_read_only_capability`: Jarvis-nahe Muster werden read-only genutzt oder nachgebaut.
- `use_as_isolated_worker`: Jarvis bekommt nach Operator-Go einen isolierten Worker-Scope.
- `adopt_selected_components`: Nur klar bessere Einzelkomponenten werden übernommen oder nachgebaut.

## Standardbefehl

```bash
python3 scripts/ops/openjarvis_decision_gauntlet.py
```

Der Befehl schreibt:

- `OPENJARVIS_DECISION_GAUNTLET.json`
- `OPENJARVIS_DECISION_GAUNTLET.md`
- `OPENJARVIS_DECISION_TEST_MATRIX.json`
- `OPENJARVIS_DECISION_WORK_ITEMS.md`
