# Workspace Placement

Status: active
Updated: 2026-05-28

## Canonical Path

```text
/Users/BjornRosinger/Documents/DreamFactory/Room16/research-agent-ops
```

This repository contains the deterministic Research Agent core, Agent-OS
readiness checks, Quellwert/Room16 operating evidence, outcome runners,
publishing guardrails and local hygiene verifiers.

## Retired Legacy Root

```text
/Users/BjornRosinger/Documents/New project 2
```

The legacy root path is retired. The old compatibility link was moved to
`/Users/BjornRosinger/Documents/Codex/path-hygiene-compatibility-links/` for
audit/history only. New scripts, docs and operator instructions must use the
canonical path.

## Rule

`/Users/BjornRosinger/Documents/New project 2` must not become a real folder or
root symlink again. `documents_root_hygiene_check.py` treats that retired root
name as an error after the migration.

## Verifier

```bash
cd "/Users/BjornRosinger/Documents/DreamFactory/Room16/research-agent-ops"
python3 scripts/ops/documents_root_hygiene_check.py --json
```
