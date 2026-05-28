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

## Legacy Compatibility

```text
/Users/BjornRosinger/Documents/New project 2
```

The legacy path is kept only as a symlink to the canonical path. New scripts,
docs and operator instructions should use the canonical path.

## Rule

`/Users/BjornRosinger/Documents/New project 2` must not become a real folder
again. `documents_root_hygiene_check.py` treats a real root folder with that
name as an error after the migration.

## Verifier

```bash
cd "/Users/BjornRosinger/Documents/DreamFactory/Room16/research-agent-ops"
python3 scripts/ops/documents_root_hygiene_check.py --json
```
