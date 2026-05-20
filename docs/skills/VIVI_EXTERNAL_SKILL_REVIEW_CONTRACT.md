# Vivi External Skill Review Contract

Status: active draft  
Scope: external skill, repo and agent-package reviews  
Created: 2026-05-20

## Purpose

Vivi reviews external skills as untrusted source material. Her review may approve pattern extraction, SOP adoption or sandbox consideration, but it must not approve direct runtime installation unless source and local artifacts were fully reviewed and a separate Operator Gate exists.

## Required Review Inputs

- source URL
- owner/source identity
- audit metadata
- local archive path
- local `SKILL.md` path
- source verification status
- unpack/review status
- relevant existing LIONCOM/Vega/Vivi/Obsidian capabilities

## Review Dimensions

Vivi must check:

- source verification
- local artifact availability
- risk class
- runtime authority
- network/API behavior
- credentials/OAuth/account access
- filesystem access
- memory behavior
- autonomous/background/update behavior
- operator gate compatibility
- Obsidian compatibility
- pattern extraction potential
- install decision

## Review Status Values

| Status | Meaning |
| --- | --- |
| `reject` | Do not use; hard risk or unsuitable. |
| `hold` | Keep as reference; no active integration. |
| `pattern_extract_only` | Extract bounded ideas only; no runtime. |
| `sandbox_candidate` | May be tested only in isolated scope with Operator-Go. |
| `approved_sop` | Safe as SOP/checklist/playbook. |
| `approved_runtime_candidate` | Candidate for a future implementation proposal, not approval to run. |

## Mandatory Output Fields

- `review_status`
- `blocking_issues`
- `non_blocking_issues`
- `useful_patterns`
- `rejected_patterns`
- `do_not_install_reasons`
- `required_operator_action`
- `codex_fix_or_doc_task`

## Hard Rules

- `source_not_verified` means no final decision.
- Slug/name-only analysis is forbidden.
- Deep Research must be checked against Obsidian, existing capabilities and Operator Gates.
- External memory systems must not bypass the Obsidian Memory Promotion Map.
- A skill with credentials, API writes, desktop control or autonomous behavior cannot be marked safe for normal runtime by Vivi alone.
- Direct install remains blocked unless a separate Operator Gate and Vega verification path exist.

## Acceptance Criteria

- Review separates pattern value from runtime authority.
- Source verification status is explicit.
- Obsidian compatibility is explicit.
- Existing local capabilities are considered.
- Recommendations stay within reject, hold, pattern extraction, SOP, sandbox or future runtime-candidate lanes.
