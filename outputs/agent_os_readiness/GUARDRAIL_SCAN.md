# Guardrail Scan

Findings: 36
Highest severity: `high`

| File | Line | Check | Severity | Gate | Evidence |
| --- | ---: | --- | --- | ---: | --- |
| `docs/OUTCOME_MATURATION_POLICY_2026-05-18.md` | 65 | `auto_runtime_mutation` | `high` | true | - Quellwert-Publish-Go, |
| `docs/OUTCOME_MATURATION_POLICY_2026-05-18.md` | 66 | `auto_runtime_mutation` | `high` | true | - Production-Go, |
| `docs/agent_os/DELIVERABLE_SWARM_OPERATING_OVERVIEW.md` | 144 | `skill_memory_write` | `high` | true | 8. Wenn dauerhafte Projektwahrheit entstanden ist, in Obsidian oder Pending Sync sichern. |
| `docs/automation/AUTOMATION_WORKFLOWS_PLAYBOOK.md` | 24 | `auto_runtime_mutation` | `high` | true | - Automatically release reports. |
| `docs/automation/AUTOMATION_WORKFLOWS_PLAYBOOK.md` | 25 | `auto_runtime_mutation` | `high` | true | - Automatically enable Ads or Affiliate. |
| `docs/automation/AUTOMATION_WORKFLOWS_PLAYBOOK.md` | 28 | `auto_runtime_mutation` | `high` | true | - Automatically publish. |
| `docs/automation/AUTOMATION_WORKFLOWS_PLAYBOOK.md` | 29 | `skill_background_or_self_modify` | `high` | true | - Automatically create runtime rights, API keys or background agents. |
| `docs/media_ingest/MEDIA_SOURCE_POLICY.md` | 4 | `skill_background_or_self_modify` | `high` | true | Applies to: Whisper / YouTube Watcher derived workflows, Room16, Quellwert, Vivi and Obsidian |
| `docs/media_ingest/MEDIA_SOURCE_POLICY.md` | 45 | `auto_runtime_mutation` | `high` | true | - SEC/filing or official release cited inside media: verify against the primary source before use. |
| `docs/media_ingest/OBSIDIAN_MEDIA_NOTE_POLICY.md` | 4 | `skill_background_or_self_modify` | `high` | true | Applies to: media notes created from Whisper / YouTube Watcher patterns |
| `docs/media_ingest/ROOM16_MEDIA_INGEST_INTEGRATION.md` | 45 | `auto_runtime_mutation` | `high` | true | - Hard financial claims from media must be checked against IR, SEC, filings, earnings release or official presentation before report use. |
| `docs/memory/OBSIDIAN_MEMORY_PROMOTION_MAP.md` | 43 | `skill_memory_write` | `high` | true | | Vivi Review or Operator-Go plus evidence | `BACKBONE` | Write the smallest durable rule into Obsidian. | |
| `docs/memory/OBSIDIAN_MEMORY_PROMOTION_MAP.md` | 94 | `auto_runtime_mutation` | `high` | true | - private, secret, credential, token, account or OAuth data in learning files |
| `docs/memory/OBSIDIAN_MEMORY_PROMOTION_MAP.md` | 96 | `skill_background_or_self_modify` | `high` | true | - background memory mutation |
| `docs/skills/CLAW_SKILL_PATTERN_DECISION_MATRIX.json` | 34 | `skill_background_or_self_modify` | `high` | true | "P1": ["github", "word-docx", "excel-xlsx", "openai-whisper", "youtube-watcher", "humanizer"], |
| `docs/skills/CLAW_SKILL_PATTERN_DECISION_MATRIX.md` | 36 | `skill_background_or_self_modify` | `high` | true | | `youtube-watcher` | yes | yes | transcript extraction pattern | source/copyright gates | transcript helper with attribution | unbounded video ingest | R3 | adopt as future playbook | P1 | 2-4d | media ingest | |
| `docs/skills/CLAW_SKILL_PATTERN_DECISION_MATRIX.md` | 56 | `skill_background_or_self_modify` | `high` | true | - `youtube-watcher` |
| `docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` | 56 | `auto_runtime_mutation` | `high` | true | - credential, secret, token, OAuth, account and environment-variable access |
| `docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` | 59 | `skill_background_or_self_modify` | `high` | true | - autonomous, proactive, scheduled, background or self-modifying behavior |
| `docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` | 98 | `skill_background_or_self_modify` | `high` | true | - silent auto-update behavior |
| `docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` | 101 | `skill_memory_write` | `high` | true | - memory overwrite outside the Obsidian Gate |
| `docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` | 106 | `skill_background_or_self_modify` | `high` | true | - autonomous background behavior that bypasses LIONCOM/Vega gates |
| `docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` | 125 | `skill_background_or_self_modify` | `high` | true | - background memory mutation outside Vivi/Vega review |
| `docs/skills/HIGH_RISK_SKILLS_HOLD_REGISTER.md` | 16 | `auto_runtime_mutation` | `high` | true | | `api-gateway` | R3/R4 | Broad external API and credential/OAuth surface. | Read-only API-gate checklist. | API write access, broad OAuth, hidden SaaS mutation. | |
| `docs/skills/HIGH_RISK_SKILLS_HOLD_REGISTER.md` | 18 | `skill_background_or_self_modify` | `high` | true | | `proactive-agent full autonomy` | R6 | Background/proactive work can bypass operator gates. | WAL-lite and verify-implementation pattern. | Autonomous feature work or public changes. | |
| `docs/skills/HIGH_RISK_SKILLS_HOLD_REGISTER.md` | 20 | `skill_background_or_self_modify` | `high` | true | | `remote skillscan/phone-home scanner` | R3/R6 | External upload, polling, silent update risk. | Local inventory/risk scan idea. | Phone-home, upload, auto-update scanner. | |
| `docs/skills/LOCAL_SKILL_INVENTORY_RISK_SCAN.json` | 17 | `skill_background_or_self_modify` | `high` | true | "auto_update", |
| `docs/skills/LOCAL_SKILL_INVENTORY_RISK_SCAN.md` | 28 | `skill_background_or_self_modify` | `high` | true | - Auto-update behavior. |
| `docs/skills/LOCAL_SKILL_INVENTORY_RISK_SCAN.md` | 29 | `skill_background_or_self_modify` | `high` | true | - Background execution. |
| `docs/skills/VIVI_EXTERNAL_SKILL_REVIEW_CONTRACT.md` | 31 | `auto_runtime_mutation` | `high` | true | - credentials/OAuth/account access |
| `docs/skills/VIVI_EXTERNAL_SKILL_REVIEW_CONTRACT.md` | 34 | `skill_background_or_self_modify` | `high` | true | - autonomous/background/update behavior |
| `scripts/skills/local_skill_inventory_scan.py` | 78 | `skill_network_or_install` | `high` | true | re.compile(r"\b(curl|wget|requests\.|fetch\(|axios\.|urllib\.request|http[s]?://)", re.I), |
| `scripts/skills/local_skill_inventory_scan.py` | 117 | `skill_background_or_self_modify` | `high` | true | "Background, daemon or scheduled behavior needs an explicit gate.", |
| `scripts/skills/local_skill_inventory_scan.py` | 118 | `skill_background_or_self_modify` | `high` | true | re.compile(r"\b(cron|daemon|background|launchctl|nohup|systemd|heartbeat|schedule)\b", re.I), |
| `scripts/skills/local_skill_inventory_scan.py` | 126 | `skill_memory_write` | `high` | true | re.compile(r"\b(Obsidian|Human Overview|Backbone|Latest Session Context|vault)\b.*\b(write|update|overwrite|sync)\b", re.I), |
| `scripts/skills/local_skill_inventory_scan.py` | 134 | `auto_runtime_mutation` | `high` | true | re.compile(r"\b(gh\s+(issue|pr|release)\s+(create|edit|comment|merge|close)|git\s+push|git\s+tag)\b", re.I), |
