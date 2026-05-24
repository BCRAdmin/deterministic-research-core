# Agent Coding Guardrails

Status: aktive lokale Playbook-Schicht
Scope: Vega / Vivi / Codex Coding-Arbeit
Runtime-Änderungen: keine

## Zweck

Diese Schicht übernimmt die nützlichen Muster aus `obra/superpowers` und
`multica-ai/andrej-karpathy-skills`, ohne deren Runtime- oder Hook-Modell zu
installieren.

Sie beantwortet eine engere Frage als der Deliverable-Swarm-Vertrag:

> Wie soll ein Coding-Agent arbeiten, damit Diffs klein bleiben, Bugs wirklich
> verstanden werden und Abschlussmeldungen belegt sind?

## Harte Übernahmeregel

Übernommen wird nur als Playbook und lokaler Vertrag:

- keine globale Plugin-Installation
- kein Session-Start-Hook
- kein Skill-Trigger-Zwang vor jeder Antwort
- keine automatische Worktree-Erstellung
- kein automatisches Subagent-Driven-Development
- kein Vendoring ohne Lizenz-/Quellenklaerung

## Guardrail-Matrix

| Guardrail | Quelle | Gate | Wann nutzen |
| --- | --- | --- | --- |
| Annahmen und Tradeoffs sichtbar machen | `karpathy-guidelines` | soft | unklare Anforderungen oder mehrere plausible Wege |
| Minimal und chirurgisch ändern | `karpathy-guidelines` | soft | jede Code-, Doku- oder Config-Änderung |
| Erfolgskriterien vor Ausführung klaeren | `karpathy-guidelines`, `superpowers:writing-plans` | soft | mehrschrittige Arbeit |
| Keine Abschlussbehauptung ohne frische Evidenz | `superpowers:verification-before-completion` | hard | vor Fertig-, Pass-, Commit-, PR- oder Handoff-Claims |
| Root Cause vor Fix | `superpowers:systematic-debugging` | hard | Bugs, Tests, Build, CI, Runtime-Anomalien |
| Branch-Abschluss explizit machen | `superpowers:finishing-a-development-branch`, `superpowers:using-git-worktrees` | situational | echte Git-/PR-/Worktree-Flows |
| Skills gegen Verhalten testen | `superpowers:writing-skills` | situational | neue oder geänderte lokale Skills/Playbooks |

## Praktische Anwendung

### Kleine klare Aufgaben

- direkt arbeiten
- minimale Änderung
- passende Verifikation
- kein Spec-/Plan-Overhead

### Bugs und CI-Fails

- Fehler komplett lesen
- reproduzierbare Spur oder Diagnosebeleg sichern
- Hypothese formulieren
- minimalen Fix setzen
- Verifikation dokumentieren

### Größere Implementierungen

- Erfolgskriterien und Verify-Befehle festhalten
- Taskliste fuehren
- Review- oder Preflight-Gate nutzen
- Abschluss erst nach frischer Evidenz

### Skill-/Playbook-Änderungen

- nicht nur Markdown oder Syntax prüfen
- Druckszenario gegen bekannte Rationalisierungen formulieren
- beobachten, ob die Regel wirklich Verhalten ändert
- dauerhaftes Learning in den passenden Human-Overview-Review-Pfad aufnehmen

## Maschinenvertrag

Die maschinenlesbare Quelle liegt in:

- `research_agent/ops/coding_guardrails.py`

Generierte Review-Artefakte:

- `outputs/agent_os_readiness/AGENT_CODING_GUARDRAILS.md`
- `outputs/agent_os_readiness/AGENT_CODING_GUARDRAILS.json`

Verifier:

```bash
.venv/bin/pytest -q research_agent/tests/test_agent_os_coding_guardrails.py
python3 scripts/ops/agent_os_readiness.py
```
