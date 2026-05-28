# Documents Root Placement Fix 2026-05-28

## Ergebnis

- Future-Guardrail ergänzt: `Rule - Documents Root Hygiene` und `/Users/BjornRosinger/Documents/AGENTS.md`.
- Root-Leaks wurden aus `/Users/BjornRosinger/Documents` entfernt oder in einen Kompatibilitätslink überführt.
- Keine aktiven Legacy-Workspaces `New project` oder `New project 2` wurden verschoben.

## Moves

- `/Users/BjornRosinger/Documents/Room 16 Reports` -> `/Users/BjornRosinger/Documents/DreamFactory/Room16/Reports` (`moved_with_legacy_symlink`): Room16 shelf is a DreamFactory/Room16 subfolder, not a Documents-root project folder.
- `/Users/BjornRosinger/Documents/wp-stb-roesinger-redesign` -> `/Users/BjornRosinger/Documents/BCR Ventures/client-prototypes/wp-stb-roesinger-redesign` (`moved`): Client website prototype belongs under BCR Ventures client prototypes.
- `/Users/BjornRosinger/Documents/docs` -> `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/docs` (`quarantined`): Root docs folder was a runtime/template leak, not a project namespace.
- `/Users/BjornRosinger/Documents/dashboard` -> `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/dashboard` (`quarantined`): Root dashboard folder was a runtime/template leak, not a project namespace.
- `/Users/BjornRosinger/Documents/prompts` -> `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/prompts` (`quarantined`): Root prompts folder was a stale prompt leak; active LIONCOM prompts remain under DreamFactory/LIONCOM/prompts.
- `/Users/BjornRosinger/Documents/New%20project` -> `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/New%20project` (`quarantined`): URL-encoded leftover from the historic New%20project path bug.
- `/Users/BjornRosinger/Documents/wp-stb-roesinger-redesign` -> `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/wp-stb-roesinger-redesign-stray-preview-logs` (`quarantined_stray_preview_logs`): A stale local-preview attempt recreated the root folder with logs only after the main prototype move.
- `/Users/BjornRosinger/Documents/wp-stb-roesinger-redesign` -> `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/wp-stb-roesinger-redesign-stray-preview-logs-2` (`quarantined_stray_preview_logs`): A stale preview retry recreated the root folder with logs only; it was quarantined before creating the compatibility symlink.
- `/Users/BjornRosinger/Documents/wp-stb-roesinger-redesign` -> `/Users/BjornRosinger/Documents/BCR Ventures/client-prototypes/wp-stb-roesinger-redesign` (`legacy_symlink_created`): Compatibility link absorbs stale preview/log callers while keeping the real prototype under BCR Ventures.

## Post-State

- `/Users/BjornRosinger/Documents/Room 16 Reports`: `symlink` -> `/Users/BjornRosinger/Documents/DreamFactory/Room16/Reports`
- `/Users/BjornRosinger/Documents/DreamFactory/Room16/Reports`: `directory`
- `/Users/BjornRosinger/Documents/wp-stb-roesinger-redesign`: `symlink` -> `/Users/BjornRosinger/Documents/BCR Ventures/client-prototypes/wp-stb-roesinger-redesign`
- `/Users/BjornRosinger/Documents/BCR Ventures/client-prototypes/wp-stb-roesinger-redesign`: `directory`
- `/Users/BjornRosinger/Documents/docs`: `missing`
- `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/docs`: `directory`
- `/Users/BjornRosinger/Documents/dashboard`: `missing`
- `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/dashboard`: `directory`
- `/Users/BjornRosinger/Documents/prompts`: `missing`
- `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/prompts`: `directory`
- `/Users/BjornRosinger/Documents/New%20project`: `missing`
- `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/New%20project`: `directory`
- `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/wp-stb-roesinger-redesign-stray-preview-logs`: `directory`
- `/Users/BjornRosinger/Documents/Codex/path-hygiene-quarantine/2026-05-28/root-leaks/wp-stb-roesinger-redesign-stray-preview-logs-2`: `directory`

## Verifier

```bash
python3 scripts/ops/documents_root_hygiene_check.py --json
```
