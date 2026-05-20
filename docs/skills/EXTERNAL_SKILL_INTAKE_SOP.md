# External Skill Intake SOP

Status: active draft  
Scope: LIONCOM / Vega / Vivi / Obsidian / Room16  
Created: 2026-05-20

## Purpose

External skills, repositories and agent packages must not be installed directly.

Every external skill must pass through Intake, Source Verification, local artifact review, Risk Review and an explicit Operator Gate before any runtime use is considered.

A useful pattern inside a skill is not permission to run the skill.

## Source Verification Rule

`source_not_verified` is pre-triage only. It is not a trust finding, install finding, backdoor finding or approval.

Final review requires:

- source URL available
- owner/source identified
- current page or repository checked
- archive or bundle downloaded when available
- `SKILL.md` or equivalent read locally
- install scripts, hooks, plugins, providers and manifests inspected when present
- Obsidian and existing LIONCOM/Vega/Vivi/Room16 capabilities considered before adoption

Slug/name-only analysis is forbidden for final decisions.

## Intake Stages

| Stage | Meaning | Allowed next move |
| --- | --- | --- |
| `submitted` | Candidate received, not trusted. | Verify source. |
| `source_verified` | Page, repo or source reachable and owner recorded. | Fetch archive or inspect repo. |
| `locally_unpacked` | Local copy exists. | Read manifest, docs and scripts. |
| `static_reviewed` | Static content reviewed without execution. | Classify risk. |
| `risk_classified` | R0-R6 assigned. | Decide pattern or hold path. |
| `pattern_extracted` | Useful internal pattern captured without installation. | Create SOP, playbook or task. |
| `rejected` | Hard reject or unsuitable. | No install. Archive evidence. |
| `sandbox_candidate` | Potentially useful but unsafe for normal runtime. | Separate sandbox plan only. |
| `approved_playbook_only` | Approved only as instruction/checklist/policy. | Docs/playbook integration. |
| `approved_runtime_candidate` | Candidate for future runtime proposal. | Separate Operator Gate plus Vega verification. |

## Mandatory Review Checklist

For each external candidate, record:

- source URL and owner
- audit status and limitations
- local archive path and hash when available
- `SKILL.md` or manifest contents
- install scripts, setup scripts, package files and hooks
- network calls and external API targets
- credential, secret, token, OAuth, account and environment-variable access
- file-system read/write scope
- memory access, identity files, Obsidian/vault access and learning files
- autonomous, proactive, scheduled, background or self-modifying behavior
- update behavior, especially silent update paths
- required permissions and host authority
- exfiltration risk
- obfuscation, `eval`, `exec`, dynamic code loading or hidden minified code
- hooks, plugins, providers, daemons, browser/desktop automation or launch agents
- whether an Operator Gate is required
- whether a safer existing local capability already covers the need

## Risk Classes

| Class | Name | Description | Default decision |
| --- | --- | --- | --- |
| R0 | doc-only pattern | Instructions, checklist or examples only. | SOP/playbook candidate. |
| R1 | local read-only | Reads local files or repo state without writes. | Review/checklist candidate. |
| R2 | local write within project | Writes bounded project files or artifacts. | Needs explicit scope and verifier. |
| R3 | external network/API | Uses external HTTP, API, search or download. | Operator Gate for runtime use. |
| R4 | credentials/OAuth/account access | Touches tokens, OAuth, accounts, paid APIs or secrets. | Hold unless narrow approved pilot. |
| R5 | desktop/browser control | Controls UI, browser, mouse, keyboard, screenshots or windows. | Sandbox only. |
| R6 | autonomous/proactive/background behavior | Schedules, updates, self-modifies, runs in background or changes memory automatically. | Hold/reject unless explicitly designed internally. |

Use the highest applicable risk class.

## Decisions

| Decision | Meaning |
| --- | --- |
| `adopt_as_sop` | Convert safe ideas into internal SOP text. No external runtime. |
| `extract_pattern_only` | Capture a bounded pattern into docs, playbooks or implementation tasks. |
| `sandbox_test` | Test only in isolated environment with explicit evidence plan. |
| `hold` | Keep as reference; no active work until a concrete need appears. |
| `reject` | Do not use. Keep evidence if it affects future reviews. |

`approved_runtime_candidate` is not runtime approval. It only means a future implementation proposal may be drafted.

## Hard Reject Criteria

Reject or hard-hold any external package with:

- silent auto-update behavior
- phone-home behavior without clear Operator-Go
- credential harvesting or broad secret reads
- memory overwrite outside the Obsidian Gate
- desktop control without sandbox
- API write access without a narrow read-only pilot first
- `eval`, `exec`, obfuscation or dynamic code loading without a reviewable reason
- unclear license, owner, source or archive provenance
- autonomous background behavior that bypasses LIONCOM/Vega gates
- broad filesystem access without bounded scope
- unverifiable install scripts or hidden hooks

## Obsidian Compatibility Gate

Obsidian is the existing long-term memory and orientation layer. External memory, learning, self-improvement or proactive-agent packages must not create a second truth layer.

Allowed:

- pattern extraction into an Obsidian-compatible promotion flow
- temporary project-local notes with explicit status
- manually reviewed rule proposals

Forbidden:

- automatic global memory updates
- overwriting Project Notes, Canonical Notes or Latest Session Context without promotion gate
- private or secret data in learning files
- background memory mutation outside Vivi/Vega review

## Output Template

```yaml
name:
source_url:
owner:
local_archive_path:
local_skill_md_path:
verified: false
verification_method:
audit_status:
risk_class:
useful_patterns:
rejected_patterns:
existing_local_capability:
integration_decision:
required_operator_action:
next_step:
evidence_artifacts:
reviewer:
reviewed_at:
```

## Acceptance Criteria

- No external skill is installed without a gate.
- `source_not_verified` cannot produce a trust or install decision.
- Obsidian is considered before any memory/self-improvement/proactive package.
- Existing local capabilities are considered before adopting an external path.
- Runtime authority is not expanded by documentation alone.
