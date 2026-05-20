# Skill Authoring Policy

Status: active draft  
Scope: internal LIONCOM / Vega / Vivi / Room16 playbooks  
Created: 2026-05-20

## Goal

Internal skills and playbooks must be short, maintainable, operator-safe and compatible with the existing LIONCOM/Vega/Vivi/Obsidian system.

This policy is for authoring internal SOPs, review checklists, Codex handoffs, local utilities and sandbox-only playbooks. It is not approval to install external skills or expand runtime permissions.

## Structure

Use progressive disclosure:

```text
skill-or-playbook/
  SKILL.md
  references/
  scripts/
  assets/
```

- `SKILL.md` contains only the core instruction.
- `references/` contains longer details and examples.
- `scripts/` contains executable helpers only when necessary, reviewed and bounded.
- `assets/` contains templates, images, fixtures or non-code support files.

## Progressive Disclosure

- Keep the main instruction short.
- Do not put long reports, changelogs or broad theory into `SKILL.md`.
- Load details on demand from `references/`.
- Include examples only when they prevent real mistakes.
- Prefer one strong checklist over many overlapping mini-docs.
- Keep risk, boundaries and verification visible in the main file.

## Required Metadata

Every internal skill/playbook must declare:

- `name`
- `purpose`
- `scope`
- `allowed_actions`
- `forbidden_actions`
- `required_inputs`
- `outputs`
- `risk_class`
- `operator_gates`
- `tests_or_verification`

Recommended optional fields:

- `owner`
- `related_projects`
- `related_docs`
- `created`
- `updated`
- `status`
- `review_cadence`

## Forbidden Patterns

Internal skills/playbooks must not contain:

- vague prompts such as "make everything better"
- unbounded "fix all" behavior
- a new memory layer outside Obsidian promotion
- silent network access
- hidden update logic
- unbounded file access
- unbounded autonomy
- credential or secret reads without explicit Operator Gate
- desktop/browser control without sandbox
- production, money, email-send, deploy, delete or account actions without explicit gate
- claims of verification without evidence

## Skill Types

| Type | Meaning | Runtime authority |
| --- | --- | --- |
| `SOP-only` | Pure policy or checklist. | None. |
| `review checklist` | Structured review flow. | None unless paired with an approved tool. |
| `codex handoff` | Generates bounded technical handoff for Vega/Codex. | None by itself. |
| `local utility` | Uses bounded local reads/writes. | Requires scope and verifier. |
| `sandbox-only` | High-risk or experimental flow. | Isolated environment only. |
| `blocked` | Known unsafe or unsuitable pattern. | No runtime use. |

## Acceptance Checklist

Before a skill/playbook is accepted:

- It is short enough to skim before use.
- It has no scope creep.
- It declares do-not-touch boundaries.
- It is testable or reviewable.
- It names outputs and evidence.
- It names risk class and operator gates.
- It is compatible with Obsidian/Backbone memory rules.
- It does not duplicate existing capabilities without reason.
- It does not install or enable anything by being documented.

## Verification Rule

Verify implementation, not intent.

A skill/playbook is accepted when:

- the scope is bounded
- forbidden actions are explicit
- JSON/YAML/schema artifacts parse if present
- scripts pass syntax checks if present
- relevant test or review evidence exists
- current behavior matches documented behavior
