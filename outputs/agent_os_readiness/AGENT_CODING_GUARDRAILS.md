# Agent Coding Guardrails

Kuratierter Transfer aus `obra/superpowers` und `multica-ai/andrej-karpathy-skills`.
Diese Schicht ist ein lokaler Playbook-Vertrag, keine Plugin-Installation und kein Session-Hook.

Status: `active_local_playbook`
Runtime-Policy: `playbook_only`
Gültig: `true`
Fehler: `keine`
Warnungen: `keine`

## Quellen

- https://github.com/obra/superpowers
- https://github.com/multica-ai/andrej-karpathy-skills

## Guardrails

| ID | Gate | Quellenmuster | Trigger | Verhalten | Evidenz |
| --- | --- | --- | --- | --- | --- |
| `state_assumptions_and_tradeoffs` | `soft` | `karpathy-guidelines` | unklare Anforderungen, mehrere plausible Loesungen oder riskante implizite Annahmen | relevante Annahmen kurz nennen<br>bei echter Mehrdeutigkeit Alternativen mit Empfehlung zeigen<br>bei unklaerbarer Blockade eine konkrete Frage stellen | assumptions note<br>chosen approach or blocker |
| `minimal_surgical_change` | `soft` | `karpathy-guidelines` | bestehenden Code, Doku oder Konfiguration ändern | nur Zeilen anfassen, die auf den Auftrag einzahlen<br>lokalen Stil und bestehende Hilfsfunktionen bevorzugen<br>keine Drive-by-Refactors oder spekulativen Abstraktionen | changed files trace to request<br>unrelated findings reported but not edited |
| `goal_driven_execution` | `soft` | `karpathy-guidelines`<br>`superpowers:writing-plans` | mehrschrittige Implementierung, Bugfix oder Review-Auftrag | kleinstes prüfbares Ziel festlegen<br>Verifikation pro Schritt benennen<br>bei größeren Änderungen Plan oder Taskliste führen | success criteria<br>verification command list |
| `root_cause_before_fix` | `hard` | `superpowers:systematic-debugging` | Bug, Testfehler, Buildfehler, Runtime-Anomalie oder wiederholter Fix-Fail | Fehler komplett lesen und reproduzierbare Spur suchen<br>aktuelle Diff-/Umgebungsveraenderungen prüfen<br>Hypothese formulieren und minimal testen<br>Fix erst nach nachvollziehbarer Ursache setzen | root cause note<br>reproduction or diagnostic evidence<br>fix verification |
| `autonomous_pattern_detection_before_completion` | `soft` | `operator_expectation_autonomy_model`<br>`documents-root-hygiene`<br>`vega-operator-learning` | Operator-Korrektur, wiederkehrender Dirt, Pfadchaos, Scope-Drift oder sauber/fertig/geschlossen-Claim | Fehlmuster klassifizieren, bevor der Einzelfix als abgeschlossen gilt<br>bestehende Regel, Verifier oder Memory-Spur suchen<br>fehlende Haertung Warn-First als Review-, Verifier- oder Memory-Delta routen<br>Documents-Root-Hygiene bei Vega/Vivi-Systemarbeit als Standard-Preflight beruecksichtigen | pattern classification<br>root cause or existing-rule check<br>verifier or memory route |
| `evidence_before_completion` | `hard` | `superpowers:verification-before-completion` | vor Erfolgsmeldung, Commit, PR, Handoff oder 'fertig'-Claim | frischen passenden Verify-Befehl ausführen<br>Output und Exit-Code lesen<br>Status nur so stark formulieren, wie die Evidenz trägt | fresh verification evidence<br>command exit status<br>remaining risk if any |
| `explicit_branch_finish` | `situational` | `superpowers:finishing-a-development-branch`<br>`superpowers:using-git-worktrees` | nach größerem Branch-/PR- oder Worktree-Task | Tests vor Abschlussoptionen frisch prüfen<br>Merge, PR, Behalten oder Verwerfen als separate Operator-Entscheidung behandeln<br>destruktive Branch-/Worktree-Aktionen nie ohne klare Freigabe | test result before finish<br>selected finish option |
| `skill_behavior_pressure_test` | `situational` | `superpowers:writing-skills` | neue oder geaenderte lokale Vega/Vivi/Codex-Skills und Playbooks | nicht nur Syntax validieren<br>Druckszenario gegen bekannte Rationalisierungen testen<br>Vorher/Nachher-Learning dokumentieren | pressure scenario<br>observed failure or pass behavior<br>updated skill rule |

## Situative Übernahmen

- `worktree_finish_menu_for_explicit_git_flows`
- `plan_review_loop_for_large_implementation`
- `skill_pressure_testing_for_local_skill_changes`

## Geblockte Defaults

Diese Muster bleiben bewusst hinter Operator-, Lizenz- oder Konflikt-Gates:

- `global_session_hook`
- `skill_trigger_before_every_reply`
- `spec_commit_for_small_tasks`
- `auto_worktree_creation`
- `auto_subagent_driven_development`
- `external_plugin_vendoring_without_license_gate`

## Nutzungsregel

- Bei kleinen klaren Aufgaben nur die minimal passende Guardrail anwenden.
- Bei Bugs ist `root_cause_before_fix` hart.
- Bei Operator-Korrektur, wiederkehrendem Dirt, Pfadchaos oder Scope-Drift ist `autonomous_pattern_detection_before_completion` Warn-First-Preflight.
- Vor Abschlussclaims ist `evidence_before_completion` hart.
- Git-/Worktree- und Skill-Test-Patterns sind situativ, nicht global.
