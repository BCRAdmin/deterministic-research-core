# Claw Skill Pattern Decision Matrix

Status: active draft  
Scope: 19 source-verified ClawHub skills reviewed for internal pattern extraction  
Created: 2026-05-20

## Baseline

- 19/19 links live checked.
- 19/19 ZIP bundles locally unpacked.
- 19/19 `SKILL.md` files available locally.
- No external skill is approved for direct installation.
- Obsidian is the Backbone memory layer.
- Existing local capabilities must be preferred before external runtime adoption.

## Decision Matrix

| Skill | Source verified | Local `SKILL.md` | Primary value | What we already do better | Pattern to extract | Reject | Risk | Decision | Priority | ETA | Target |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| `skill-vetter` | yes | yes | Security review checklist | Operator Gates and source-heavy VQG | External skill intake questions | install authority | R1 | adopt as SOP | P0 | 0.5-1d | `docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` |
| `self-improving-agent` | yes | yes | Recurring learning capture | Obsidian Backbone and VQG | pattern keys, recurrence counts, evidence promotion | hooks/scripts/parallel memory | R6 | extract gated patterns only | P0 | 1-2d | `docs/memory/OBSIDIAN_MEMORY_PROMOTION_MAP.md` |
| `github` | yes | yes | `gh` CLI workflow patterns | existing GitHub plugin and repo gates | read-first commands and mutation gates | broad API mutation | R3 | adopt as playbook | P1 | 1d | GitHub Ops playbook |
| `skillscan` | yes | yes | scanner/checker idea | local review and no-phone-home posture | inventory/checklist ideas | remote API, silent updates, pending audit | R6 | hold/reject as-is | Hold | later | no runtime |
| `humanizer` | yes | yes | style lint checklist | source truth and non-advice controls | anti-slop lint | auto-rewriting research truth | R2 | adopt as lint playbook | P1 | 0.5-1d | copy lint checklist |
| `multi-search-engine` | yes | yes | query pattern breadth | source gates and citations | query syntax ideas | cookie/header scraping backbone | R3 | reject default engine | Hold | none | source-gate notes |
| `nano-pdf` | yes | yes | PDF operation ideas | Documents/PDF render checks | verify-after-edit ideas | new CLI without verifier | R2 | later/sandbox compare | P2 | 2-3d | PDF comparison |
| `nano-banana-pro` | yes | yes | image workflow | existing imagegen capability and gates | draft/iterate/final pattern | external API/credentials | R4 | later/sandbox only | P2 | later | optional visual pilot |
| `obsidian` | yes | yes | Obsidian CLI examples | Obsidian already Backbone | safe CLI examples if missing | parallel vault rules | R2 | later compare only | P2 | 1d | Obsidian comparison |
| `skill-creator` | yes | yes | progressive disclosure authoring | local skill-creator and policy control | metadata and split structure | foreign packaging/install flow | R2 | adopt as policy pattern | P0 | 0.5-1d | `docs/skills/SKILL_AUTHORING_POLICY.md` |
| `proactive-agent` | yes | yes | WAL and verification ideas | autonomy rails and Operator Gates | WAL-lite, verify implementation not intent | full autonomy/background crons/memory mutation | R6 | extract tiny patterns only | Hold | included | memory map |
| `self-improving` | yes | yes | tiered memory and heartbeat ideas | Obsidian Project Notes truth | HOT/WARM/COLD and 3x threshold | global home memory | R6 | extract gated patterns only | P0 | 1-2d | memory map |
| `api-gateway` | yes | yes | API gateway reference | explicit app-specific gates | read-only pilot rubric later | credentials, writes, broad connector runtime | R4 | hard hold runtime | Hold | none | no runtime |
| `desktop-control` | yes | yes | desktop automation concept | host authority stays gated | sandbox requirements | mouse/keyboard/screenshot control | R5 | hard hold runtime | Hold | none | no runtime |
| `word-docx` | yes | yes | DOCX handling patterns | Documents render-and-verify | OOXML caution checklist | separate foreign runtime | R2 | adopt as playbook | P1 | 2-3d | Documents workflow |
| `openai-whisper` | yes | yes | local transcription pattern | gate discipline | bounded audio ingest | immediate install | R2 | adopt as future playbook | P1 | 2-4d | media ingest |
| `youtube-watcher` | yes | yes | transcript extraction pattern | source/copyright gates | transcript helper with attribution | unbounded video ingest | R3 | adopt as future playbook | P1 | 2-4d | media ingest |
| `automation-workflows` | yes | yes | ROI intake rubric | autonomy rails and scope closure | business ROI checklist | broad autonomy rules | R6 | later rubric only | P2 | 0.5-1d | automation intake |
| `excel-xlsx` | yes | yes | XLSX handling patterns | Spreadsheets workflow | workbook-safety checklist | separate foreign runtime | R2 | adopt as playbook | P1 | 2-3d | Spreadsheets workflow |

## Priority Summary

P0 pattern package:

- `skill-vetter`
- `skill-creator`
- `self-improving-agent` gated patterns
- `self-improving` tiered memory/heartbeat patterns
- `proactive-agent` WAL-lite and verify-implementation patterns only

P1 playbook candidates:

- `github`
- `word-docx`
- `excel-xlsx`
- `openai-whisper`
- `youtube-watcher`
- `humanizer`

P2 later/sandbox/reference only:

- `nano-banana-pro`
- `nano-pdf`
- `obsidian`
- `automation-workflows`

Hold/reject:

- `skillscan` as-is
- `multi-search-engine` as default search backbone
- `proactive-agent` full autonomy
- `api-gateway` runtime
- `desktop-control` runtime

## ETA Rule

ETAs start only when a task is visible in the active workspace and claimable. Source-queue ideas are not counted as active execution unless the active runtime workspace can see and claim them.
