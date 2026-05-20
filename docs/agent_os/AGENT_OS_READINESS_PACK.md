# Agent OS Readiness Pack

Status: active local v1  
Scope: LIONCOM / Vega / Vivi / OpenClaw / Hermes pattern adoption  
Runtime changes: none

## Purpose

This pack translates the useful Hermes Agent patterns into safe local operating
surfaces:

- readiness and migration dry-run
- local skill registry
- memory inbox and local search
- automation job cards
- guardrails-as-code
- operator inbox contract
- terminal backend contracts

It is intentionally not a gateway, not an external skill installer, not a secret
importer, and not an autonomous background agent.

## Command

```bash
python3 scripts/ops/agent_os_readiness.py
```

Default outputs are written to `outputs/agent_os_readiness/`.

## Output Contract

- `AGENT_OS_READINESS_REPORT.md/json`: capability matrix and OpenClaw migration dry-run.
- `SKILL_REGISTRY.md/json`: local skill/playbook inventory with risk class and runtime decision.
- `MEMORY_INBOX_CANDIDATES.md/json`: promotion candidates for Obsidian review.
- `SESSION_SEARCH.sqlite`: local markdown search index.
- `SESSION_SEARCH_SAMPLE.json`: sample search result set.
- `AUTOMATION_JOB_CARDS.md/json`: proposed safe automation cards, not installed automations.
- `OPERATOR_INBOX.md/json`: local review inbox, not a chat gateway.
- `TERMINAL_BACKENDS.md/json`: local/Docker backend contracts, not running backends.
- `GUARDRAIL_SCAN.md/json`: local static guardrail findings.
- `RUN_SUMMARY.json`: machine-readable run summary.

## Hard Boundaries

- No external skills are installed.
- No API keys or secret values are read into output.
- No runtime config is changed.
- No Obsidian canonical note is updated by the script.
- No automation is created by the script.
- No network calls are made.

## Adoption Rule

Hermes is treated as a product-pattern benchmark. Any feature that would add
network, credentials, background execution, desktop/browser control, or canonical
memory mutation remains behind the existing External Skill Intake SOP and
Operator Gate.
