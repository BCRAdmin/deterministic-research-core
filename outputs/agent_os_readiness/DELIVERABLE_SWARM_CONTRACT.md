# Deliverable-Swarm-Vertrag

Das ist die sichere lokale Übernahme des OpenSwarm-Musters: sichtbare Spezialisten-Lanes und explizite Output-Verträge, ohne externe Runtime-Installation.

Gültig: `true`
Fehler: `keine`
Warnungen: `keine`

## Lane-Matrix

| Lane | Status | Risiko | Gate | Standard-Output | Verifier | Handoff-Ziele |
| --- | --- | --- | ---: | --- | --- | --- |
| `orchestrator` | `active_local_contract` | `R1_local_coordination` | false | `outputs/deliverable_swarm/orchestrator` | `validate_route_has_lane_owner_output_path_and_gate` | `assistant, research, data, docs, slides, images, video` |
| `assistant` | `active_local_contract` | `R2_operator_action_surface` | true | `outputs/deliverable_swarm/assistant` | `validate_no_irreversible_action_without_operator_go` | `orchestrator` |
| `research` | `active_local_contract` | `R2_external_information` | false | `outputs/deliverable_swarm/research` | `validate_claims_have_sources_and_open_questions` | `orchestrator, docs, slides, data` |
| `data` | `active_local_contract` | `R2_local_analysis` | false | `outputs/deliverable_swarm/data` | `validate_inputs_metrics_chart_paths_and_data_limits` | `orchestrator, docs, slides` |
| `docs` | `active_local_contract` | `R2_local_artifact_write` | false | `outputs/deliverable_swarm/docs` | `validate_source_html_or_markdown_export_and_change_summary` | `orchestrator, research, data` |
| `slides` | `active_local_contract` | `R2_local_artifact_write` | false | `outputs/deliverable_swarm/slides` | `validate_deck_export_visual_qa_and_no_overflow` | `orchestrator, research, data` |
| `images` | `provider_gated_contract` | `R3_external_media_provider` | true | `outputs/deliverable_swarm/images` | `validate_prompt_reference_rights_output_path_and_qc` | `orchestrator, docs, slides` |
| `video` | `provider_gated_contract` | `R3_external_media_provider` | true | `outputs/deliverable_swarm/video` | `validate_brief_duration_provider_cost_output_path_and_qc` | `orchestrator, images` |

## Output-Verträge

| Vertrag | Lane | Artefakt | Standardpfad | Gate-Regel | Prüfung |
| --- | --- | --- | --- | --- | --- |
| `route-plan` | `orchestrator` | `route_plan` | `outputs/deliverable_swarm/orchestrator/{project}/route_plan.md` | `local_verification_required` | `validate_route_has_lane_owner_output_path_and_gate, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `handoff-packet` | `orchestrator` | `handoff_packet` | `outputs/deliverable_swarm/orchestrator/{project}/handoff_packet.json` | `local_verification_required` | `validate_route_has_lane_owner_output_path_and_gate, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `operator-note` | `assistant` | `operator_note` | `outputs/deliverable_swarm/assistant/{project}/operator_note.md` | `operator_go_required` | `validate_no_irreversible_action_without_operator_go, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `draft-message` | `assistant` | `draft_message` | `outputs/deliverable_swarm/assistant/{project}/draft_message.md` | `operator_go_required` | `validate_no_irreversible_action_without_operator_go, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `task-summary` | `assistant` | `task_summary` | `outputs/deliverable_swarm/assistant/{project}/task_summary.md` | `operator_go_required` | `validate_no_irreversible_action_without_operator_go, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `research-brief` | `research` | `research_brief` | `outputs/deliverable_swarm/research/{project}/research_brief.md` | `local_verification_required` | `validate_claims_have_sources_and_open_questions, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `source-matrix` | `research` | `source_matrix` | `outputs/deliverable_swarm/research/{project}/source_matrix.json` | `local_verification_required` | `validate_claims_have_sources_and_open_questions, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `decision-options` | `research` | `decision_options` | `outputs/deliverable_swarm/research/{project}/decision_options.md` | `local_verification_required` | `validate_claims_have_sources_and_open_questions, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `analysis-report` | `data` | `analysis_report` | `outputs/deliverable_swarm/data/{project}/analysis_report.md` | `local_verification_required` | `validate_inputs_metrics_chart_paths_and_data_limits, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `chart-asset` | `data` | `chart_asset` | `outputs/deliverable_swarm/data/{project}/charts/{artifact_id}.png` | `local_verification_required` | `validate_inputs_metrics_chart_paths_and_data_limits, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `data-quality-note` | `data` | `data_quality_note` | `outputs/deliverable_swarm/data/{project}/data_quality_note.md` | `local_verification_required` | `validate_inputs_metrics_chart_paths_and_data_limits, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `markdown-doc` | `docs` | `markdown_doc` | `outputs/deliverable_swarm/docs/{project}/document.md` | `local_verification_required` | `validate_source_html_or_markdown_export_and_change_summary, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `docx-doc` | `docs` | `docx_doc` | `outputs/deliverable_swarm/docs/{project}/document.docx` | `local_verification_required` | `validate_source_html_or_markdown_export_and_change_summary, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `pdf-doc` | `docs` | `pdf_doc` | `outputs/deliverable_swarm/docs/{project}/document.pdf` | `local_verification_required` | `validate_source_html_or_markdown_export_and_change_summary, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `change-summary` | `docs` | `change_summary` | `outputs/deliverable_swarm/docs/{project}/change_summary.md` | `local_verification_required` | `validate_source_html_or_markdown_export_and_change_summary, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `slide-source` | `slides` | `slide_source` | `outputs/deliverable_swarm/slides/{project}/slides/slide_manifest.json` | `local_verification_required` | `validate_deck_export_visual_qa_and_no_overflow, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `pptx-deck` | `slides` | `pptx_deck` | `outputs/deliverable_swarm/slides/{project}/deck.pptx` | `local_verification_required` | `validate_deck_export_visual_qa_and_no_overflow, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `deck-visual-qa` | `slides` | `deck_visual_qa` | `outputs/deliverable_swarm/slides/{project}/visual_qa.md` | `local_verification_required` | `validate_deck_export_visual_qa_and_no_overflow, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `image-asset` | `images` | `image_asset` | `outputs/deliverable_swarm/images/{project}/images/{artifact_id}.png` | `operator_go_required` | `validate_prompt_reference_rights_output_path_and_qc, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `image-qc-report` | `images` | `image_qc_report` | `outputs/deliverable_swarm/images/{project}/image_qc_report.md` | `operator_go_required` | `validate_prompt_reference_rights_output_path_and_qc, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `video-asset` | `video` | `video_asset` | `outputs/deliverable_swarm/video/{project}/videos/{artifact_id}.mp4` | `operator_go_required` | `validate_brief_duration_provider_cost_output_path_and_qc, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |
| `video-qc-report` | `video` | `video_qc_report` | `outputs/deliverable_swarm/video/{project}/video_qc_report.md` | `operator_go_required` | `validate_brief_duration_provider_cost_output_path_and_qc, git_diff_check_for_repo_outputs_when_applicable, operator_gate_check_if_required` |

## Harte Grenzen

- `auto_install_external_runtime`
- `auto_install_system_packages`
- `auto_connect_external_accounts`
- `auto_import_secrets`
- `auto_publish_public_outputs`
- `auto_write_canonical_memory`
- `auto_create_background_automation`
- `unbounded_all_to_all_handoff`

## Übernahmeregel

Nutze diesen Vertrag als erste sichtbare Fähigkeitsoberfläche für LIONCOM/Vivi/OpenClaw. Er darf Arbeit an bestehende lokale Skills und geprüfte Artefakt-Workflows routen, installiert aber weder OpenSwarm noch Composio, Systempakete oder Hintergrundagenten.
