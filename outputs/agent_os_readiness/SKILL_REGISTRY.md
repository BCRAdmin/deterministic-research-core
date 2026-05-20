# Local Agent Skill Registry

This registry is a review surface, not a runtime installer.

Records: 26

## Decision Counts

- `approved_local_review_helper`: 1
- `approved_playbook_only`: 12
- `hold_for_operator_review`: 11
- `review_before_runtime_use`: 2

## Registry

| Skill ID | Title | Risk | Decision | Gate | Findings | Path |
| --- | --- | --- | --- | ---: | ---: | --- |
| `docx-workflow-playbook-8e04651f` | DOCX Workflow Playbook | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/documents/DOCX_WORKFLOW_PLAYBOOK.md` |
| `media-claim-extraction-workflow-7a8f3a84` | Media Claim Extraction Workflow | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/media_ingest/MEDIA_CLAIM_EXTRACTION_WORKFLOW.md` |
| `media-ingest-use-cases-9456c898` | Media Ingest Use Cases | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/media_ingest/MEDIA_INGEST_USE_CASES.md` |
| `next-media-sample-backlog-cc257d7c` | Next Media Sample Backlog | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/media_ingest/NEXT_MEDIA_SAMPLE_BACKLOG.md` |
| `transcription-workflow-794a8099` | Transcription Workflow | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/media_ingest/TRANSCRIPTION_WORKFLOW.md` |
| `vivi-media-ingest-review-9d60878a` | Vivi Media Ingest Review | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/media_ingest/VIVI_MEDIA_INGEST_REVIEW.md` |
| `pdf-render-playbook-cb94e08e` | PDF Render Playbook | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/pdf/PDF_RENDER_PLAYBOOK.md` |
| `external-skill-intake-package-a0f125f2` | External Skill Intake Package | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/skills/EXTERNAL_SKILL_INTAKE_PACKAGE_README.md` |
| `skill-authoring-policy-3c0ef209` | Skill Authoring Policy | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/skills/SKILL_AUTHORING_POLICY.md` |
| `xlsx-workflow-playbook-16a0e124` | XLSX Workflow Playbook | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/spreadsheets/XLSX_WORKFLOW_PLAYBOOK.md` |
| `humanizer-lint-playbook-1366dda5` | Humanizer Lint Playbook | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `docs/writing/HUMANIZER_LINT_PLAYBOOK.md` |
| `media-ingest-helper-scripts-25212885` | Media Ingest Helper Scripts | `R0_doc_only_pattern` | `approved_playbook_only` | false | 0 | `scripts/media_ingest/README.md` |
| `validate-transcript-metadata-b9019b41` | Validate Transcript Metadata | `R1_local_read_only_helper` | `approved_local_review_helper` | false | 0 | `scripts/media_ingest/validate_transcript_metadata.py` |
| `transcript-clean-fc425d3c` | Transcript Clean | `R2_local_write_or_exec_helper` | `review_before_runtime_use` | true | 0 | `scripts/media_ingest/prepare_media_ingest_folder.sh` |
| `agent-os-readiness-ef832283` | Agent Os Readiness | `R2_local_write_or_exec_helper` | `review_before_runtime_use` | true | 0 | `scripts/ops/agent_os_readiness.py` |
| `automation-workflows-playbook-dc8fc5cb` | Automation Workflows Playbook | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 4 | `docs/automation/AUTOMATION_WORKFLOWS_PLAYBOOK.md` |
| `media-source-policy-3188eac1` | Media Source Policy | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 2 | `docs/media_ingest/MEDIA_SOURCE_POLICY.md` |
| `obsidian-media-note-policy-845205e4` | Obsidian Media Note Policy | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 1 | `docs/media_ingest/OBSIDIAN_MEDIA_NOTE_POLICY.md` |
| `room16-media-ingest-integration-56de43ac` | Room16 Media Ingest Integration | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 1 | `docs/media_ingest/ROOM16_MEDIA_INGEST_INTEGRATION.md` |
| `obsidian-memory-promotion-map-dfb49ae7` | Obsidian Memory Promotion Map | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 3 | `docs/memory/OBSIDIAN_MEMORY_PROMOTION_MAP.md` |
| `claw-skill-pattern-decision-matrix-45874645` | Claw Skill Pattern Decision Matrix | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 2 | `docs/skills/CLAW_SKILL_PATTERN_DECISION_MATRIX.md` |
| `external-skill-intake-sop-272f1a44` | External Skill Intake SOP | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 5 | `docs/skills/EXTERNAL_SKILL_INTAKE_SOP.md` |
| `high-risk-skills-hold-register-dc54d318` | High-Risk Skills Hold Register | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 2 | `docs/skills/HIGH_RISK_SKILLS_HOLD_REGISTER.md` |
| `local-skill-inventory-risk-scan-aeac00dc` | Local Skill Inventory Risk Scan | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 2 | `docs/skills/LOCAL_SKILL_INVENTORY_RISK_SCAN.md` |
| `vivi-external-skill-review-contract-a0943bae` | Vivi External Skill Review Contract | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 1 | `docs/skills/VIVI_EXTERNAL_SKILL_REVIEW_CONTRACT.md` |
| `local-skill-inventory-scan-7cb34f41` | Local Skill Inventory Scan | `R6_autonomous_or_background` | `hold_for_operator_review` | true | 4 | `scripts/skills/local_skill_inventory_scan.py` |
