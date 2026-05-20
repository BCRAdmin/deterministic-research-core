# High-Risk Skills Hold Register

Status: active
Scope: external high-risk skill patterns
Risk class: R3-R6 hold
Runtime changes: none

## Purpose

Keep high-risk external skill patterns explicitly on hold so they are not later introduced by implication, drift or convenience.

## Hold Items

| Pattern | Risk class | Why hold | Allowed extraction | Forbidden runtime behavior |
| --- | --- | --- | --- | --- |
| `api-gateway` | R3/R4 | Broad external API and credential/OAuth surface. | Read-only API-gate checklist. | API write access, broad OAuth, hidden SaaS mutation. |
| `desktop-control` | R5 | Host UI, browser, keyboard and screenshot authority. | Sandbox checklist only. | Unsandboxed desktop/browser control. |
| `proactive-agent full autonomy` | R6 | Background/proactive work can bypass operator gates. | WAL-lite and verify-implementation pattern. | Autonomous feature work or public changes. |
| `external self-improving runtime` | R6 | Can create second memory layer or mutate behavior. | Obsidian promotion pattern only. | Runtime self-modification or global memory writes. |
| `remote skillscan/phone-home scanner` | R3/R6 | External upload, polling, silent update risk. | Local inventory/risk scan idea. | Phone-home, upload, auto-update scanner. |

## Future Sandbox Conditions

Any future sandbox requires:

- source verification
- local artifact review
- risk class
- explicit operator gate
- no credentials unless separately approved
- no production data
- bounded write scope
- rollback/no-rollback note
- Vivi or Vega review evidence

## Operator Gate

All hold items require explicit operator approval before any runtime pilot. Documentation alone does not approve runtime use.
