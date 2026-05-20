# Local Skill Inventory Risk Scan

Status: active draft
Scope: local docs and helper inventory
Risk class: R1 local read-only
Runtime changes: none

## Purpose

Capture the useful SkillScan pattern as a local-only inventory and risk scan. This is not an external scanner, not an audit authority and not approval to install or run anything.

## Scan Scope

- `docs/skills`
- `docs/media_ingest`
- `docs/github`
- `scripts/`

The scan must not upload files, call external APIs, phone home or auto-update.

## Checks

- Executable scripts.
- Network calls.
- Filesystem writes.
- Credential references.
- Environment variables.
- Auto-update behavior.
- Background execution.
- Obsidian writes.
- GitHub mutations.
- API calls.

## Risk Output

Each finding should include:

- `file`
- `line`
- `risk_type`
- `severity`
- `reason`
- `allowed`
- `operator_gate_needed`

Do not print secret values. Findings should report category and location only.

## Optional Helper

Use `scripts/skills/local_skill_inventory_scan.py` for a local, read-only scan.

Rules:

- local only
- no network
- read-only
- stdout JSON or Markdown
- no secret printing

## Limits

This scan is a triage aid. It does not replace External Skill Intake SOP, Vivi review or Operator-Go.
