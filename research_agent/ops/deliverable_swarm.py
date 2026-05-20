"""Deliverable Swarm contract.

OpenSwarm's strongest reusable pattern is not its runtime installer. It is the
simple product surface: one orchestrator and visible specialist lanes for
concrete deliverables. This module turns that pattern into a bounded local
contract for Vega/LIONCOM/Vivi.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence


DEFAULT_BLOCKED_ACTIONS = (
    "auto_install_external_runtime",
    "auto_install_system_packages",
    "auto_connect_external_accounts",
    "auto_import_secrets",
    "auto_publish_public_outputs",
    "auto_write_canonical_memory",
    "auto_create_background_automation",
    "unbounded_all_to_all_handoff",
)

REQUIRED_LANES = (
    "orchestrator",
    "assistant",
    "research",
    "data",
    "docs",
    "slides",
    "images",
    "video",
)

REQUIRED_CONTRACT_METADATA = (
    "artifact_id",
    "lane_id",
    "artifact_type",
    "output_path",
    "status",
    "verifier",
    "blocked_gates",
    "next_action",
)

FORBIDDEN_TOOLSET_TOKENS = (
    "auto_install",
    "system_package_install",
    "composio_unbounded",
    "all_to_all_handoff",
    "secret_read",
    "desktop_control",
    "background_agent",
)


@dataclass(frozen=True)
class DeliverableLane:
    lane_id: str
    title: str
    status: str
    owner_role: str
    purpose: str
    triggers: tuple[str, ...]
    default_output_dir: str
    artifact_types: tuple[str, ...]
    allowed_toolsets: tuple[str, ...]
    verifier: str
    finality_rule: str
    risk_class: str
    operator_gate_required: bool
    handoff_targets: tuple[str, ...]
    blocked_actions: tuple[str, ...] = DEFAULT_BLOCKED_ACTIONS

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DeliveryContract:
    contract_id: str
    lane_id: str
    artifact_type: str
    default_path_template: str
    required_metadata: tuple[str, ...]
    required_verification: tuple[str, ...]
    final_status_values: tuple[str, ...]
    delivery_rule: str
    gate_rule: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SwarmValidation:
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _safe_output_path(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and path.parts[:1] == ("outputs",)


def default_deliverable_lanes(root: Path) -> list[DeliverableLane]:
    root = root.resolve()
    del root
    return [
        DeliverableLane(
            lane_id="orchestrator",
            title="Orchestrator",
            status="active_local_contract",
            owner_role="Vega supervisor / LIONCOM route planner",
            purpose="Classify the request, choose lanes, define output contract, and route work.",
            triggers=("multi-step request", "unclear owner", "cross-lane deliverable package"),
            default_output_dir="outputs/deliverable_swarm/orchestrator",
            artifact_types=("route_plan", "handoff_packet"),
            allowed_toolsets=("read_file", "search_files", "terminal_read_only"),
            verifier="validate_route_has_lane_owner_output_path_and_gate",
            finality_rule="Never claim final delivery; specialists and verifiers own final artifacts.",
            risk_class="R1_local_coordination",
            operator_gate_required=False,
            handoff_targets=("assistant", "research", "data", "docs", "slides", "images", "video"),
        ),
        DeliverableLane(
            lane_id="assistant",
            title="Assistant",
            status="active_local_contract",
            owner_role="Vivi operator assistant",
            purpose="Draft messages, summarize small tasks, and coordinate operator-facing follow-up.",
            triggers=("admin task", "message draft", "operator summary", "small coordination task"),
            default_output_dir="outputs/deliverable_swarm/assistant",
            artifact_types=("operator_note", "draft_message", "task_summary"),
            allowed_toolsets=("read_file", "search_files"),
            verifier="validate_no_irreversible_action_without_operator_go",
            finality_rule="Drafts are reviewable until the operator explicitly approves sending or mutation.",
            risk_class="R2_operator_action_surface",
            operator_gate_required=True,
            handoff_targets=("orchestrator",),
        ),
        DeliverableLane(
            lane_id="research",
            title="Deep Research",
            status="active_local_contract",
            owner_role="Vega research lane",
            purpose="Produce cited research briefs and source-backed decision options.",
            triggers=("deep research", "competitor analysis", "repo scan", "market/source review"),
            default_output_dir="outputs/deliverable_swarm/research",
            artifact_types=("research_brief", "source_matrix", "decision_options"),
            allowed_toolsets=("read_file", "search_files", "web_search_with_citation_policy"),
            verifier="validate_claims_have_sources_and_open_questions",
            finality_rule="Facts are final only after source attribution and uncertainty notes are present.",
            risk_class="R2_external_information",
            operator_gate_required=False,
            handoff_targets=("orchestrator", "docs", "slides", "data"),
        ),
        DeliverableLane(
            lane_id="data",
            title="Data Analyst",
            status="active_local_contract",
            owner_role="Room16 / deterministic data lane",
            purpose="Analyze structured data, produce charts, and report assumptions and limits.",
            triggers=("csv", "xlsx", "metrics", "chart", "statistical analysis", "dashboard input"),
            default_output_dir="outputs/deliverable_swarm/data",
            artifact_types=("analysis_report", "chart_asset", "data_quality_note"),
            allowed_toolsets=("read_file", "local_python_analysis", "terminal_read_only"),
            verifier="validate_inputs_metrics_chart_paths_and_data_limits",
            finality_rule="Data outputs are final only with source period, assumptions, and validation notes.",
            risk_class="R2_local_analysis",
            operator_gate_required=False,
            handoff_targets=("orchestrator", "docs", "slides"),
        ),
        DeliverableLane(
            lane_id="docs",
            title="Docs",
            status="active_local_contract",
            owner_role="Document artifact lane",
            purpose="Create or update markdown, DOCX, PDF, SOP, and report documents.",
            triggers=("document", "docx", "pdf", "sop", "report", "brief"),
            default_output_dir="outputs/deliverable_swarm/docs",
            artifact_types=("markdown_doc", "docx_doc", "pdf_doc", "change_summary"),
            allowed_toolsets=("read_file", "local_file_write_artifact", "document_render_verify"),
            verifier="validate_source_html_or_markdown_export_and_change_summary",
            finality_rule="Document outputs need explicit output path and render/export verification.",
            risk_class="R2_local_artifact_write",
            operator_gate_required=False,
            handoff_targets=("orchestrator", "research", "data"),
        ),
        DeliverableLane(
            lane_id="slides",
            title="Slides",
            status="active_local_contract",
            owner_role="Presentation artifact lane",
            purpose="Create slide decks with source slides, exported PPTX/PDF, and visual QA.",
            triggers=("presentation", "slides", "deck", "pitch", "pptx"),
            default_output_dir="outputs/deliverable_swarm/slides",
            artifact_types=("slide_source", "pptx_deck", "deck_visual_qa"),
            allowed_toolsets=("read_file", "local_file_write_artifact", "presentation_render_verify"),
            verifier="validate_deck_export_visual_qa_and_no_overflow",
            finality_rule="Decks are final only after export and visual QA artifact exists.",
            risk_class="R2_local_artifact_write",
            operator_gate_required=False,
            handoff_targets=("orchestrator", "research", "data"),
        ),
        DeliverableLane(
            lane_id="images",
            title="Images",
            status="provider_gated_contract",
            owner_role="Visual generation lane",
            purpose="Generate or edit images only when model/provider and rights gates are clear.",
            triggers=("image", "visual", "hero asset", "photo edit", "mockup"),
            default_output_dir="outputs/deliverable_swarm/images",
            artifact_types=("image_asset", "image_qc_report"),
            allowed_toolsets=("local_asset_review", "provider_image_generation_after_gate"),
            verifier="validate_prompt_reference_rights_output_path_and_qc",
            finality_rule="Image outputs are final only after QC pass and rights/source notes.",
            risk_class="R3_external_media_provider",
            operator_gate_required=True,
            handoff_targets=("orchestrator", "docs", "slides"),
        ),
        DeliverableLane(
            lane_id="video",
            title="Video",
            status="provider_gated_contract",
            owner_role="Video generation lane",
            purpose="Generate or edit video only behind provider, cost, duration, and QC gates.",
            triggers=("video", "clip", "animation", "voiceover", "subtitles"),
            default_output_dir="outputs/deliverable_swarm/video",
            artifact_types=("video_asset", "video_qc_report"),
            allowed_toolsets=("local_asset_review", "provider_video_generation_after_gate"),
            verifier="validate_brief_duration_provider_cost_output_path_and_qc",
            finality_rule="Video outputs are final only after rendered file and QC evidence exist.",
            risk_class="R3_external_media_provider",
            operator_gate_required=True,
            handoff_targets=("orchestrator", "images"),
        ),
    ]


def default_delivery_contracts(root: Path) -> list[DeliveryContract]:
    lanes = {lane.lane_id: lane for lane in default_deliverable_lanes(root)}
    specs = [
        ("route-plan", "orchestrator", "route_plan", "route_plan.md"),
        ("handoff-packet", "orchestrator", "handoff_packet", "handoff_packet.json"),
        ("operator-note", "assistant", "operator_note", "operator_note.md"),
        ("draft-message", "assistant", "draft_message", "draft_message.md"),
        ("task-summary", "assistant", "task_summary", "task_summary.md"),
        ("research-brief", "research", "research_brief", "research_brief.md"),
        ("source-matrix", "research", "source_matrix", "source_matrix.json"),
        ("decision-options", "research", "decision_options", "decision_options.md"),
        ("analysis-report", "data", "analysis_report", "analysis_report.md"),
        ("chart-asset", "data", "chart_asset", "charts/{artifact_id}.png"),
        ("data-quality-note", "data", "data_quality_note", "data_quality_note.md"),
        ("markdown-doc", "docs", "markdown_doc", "document.md"),
        ("docx-doc", "docs", "docx_doc", "document.docx"),
        ("pdf-doc", "docs", "pdf_doc", "document.pdf"),
        ("change-summary", "docs", "change_summary", "change_summary.md"),
        ("slide-source", "slides", "slide_source", "slides/slide_manifest.json"),
        ("pptx-deck", "slides", "pptx_deck", "deck.pptx"),
        ("deck-visual-qa", "slides", "deck_visual_qa", "visual_qa.md"),
        ("image-asset", "images", "image_asset", "images/{artifact_id}.png"),
        ("image-qc-report", "images", "image_qc_report", "image_qc_report.md"),
        ("video-asset", "video", "video_asset", "videos/{artifact_id}.mp4"),
        ("video-qc-report", "video", "video_qc_report", "video_qc_report.md"),
    ]
    contracts: list[DeliveryContract] = []
    for contract_id, lane_id, artifact_type, suffix in specs:
        lane = lanes[lane_id]
        contracts.append(
            DeliveryContract(
                contract_id=contract_id,
                lane_id=lane_id,
                artifact_type=artifact_type,
                default_path_template=f"{lane.default_output_dir}/{{project}}/{suffix}",
                required_metadata=REQUIRED_CONTRACT_METADATA,
                required_verification=(
                    lane.verifier,
                    "git_diff_check_for_repo_outputs_when_applicable",
                    "operator_gate_check_if_required",
                ),
                final_status_values=("draft", "internal_best", "verified", "blocked"),
                delivery_rule="include_absolute_or_repo_relative_output_path_in_final_response",
                gate_rule=(
                    "operator_go_required"
                    if lane.operator_gate_required
                    else "local_verification_required"
                ),
            )
        )
    return contracts


def validate_deliverable_swarm(
    lanes: Sequence[DeliverableLane],
    contracts: Sequence[DeliveryContract],
    root: Path,
) -> SwarmValidation:
    root = root.resolve()
    del root
    errors: list[str] = []
    warnings: list[str] = []

    lane_ids = [lane.lane_id for lane in lanes]
    duplicate_lanes = sorted({lane_id for lane_id in lane_ids if lane_ids.count(lane_id) > 1})
    for lane_id in duplicate_lanes:
        errors.append(f"duplicate_lane_id:{lane_id}")

    missing_lanes = [lane_id for lane_id in REQUIRED_LANES if lane_id not in lane_ids]
    for lane_id in missing_lanes:
        errors.append(f"missing_required_lane:{lane_id}")

    lanes_by_id = {lane.lane_id: lane for lane in lanes}
    orchestrator = lanes_by_id.get("orchestrator")
    if orchestrator:
        expected_targets = tuple(lane_id for lane_id in REQUIRED_LANES if lane_id != "orchestrator")
        if tuple(sorted(orchestrator.handoff_targets)) != tuple(sorted(expected_targets)):
            errors.append("orchestrator_must_route_to_every_specialist_lane")

    for lane in lanes:
        if not lane.title or not lane.owner_role or not lane.purpose:
            errors.append(f"lane_missing_identity:{lane.lane_id}")
        if not lane.artifact_types:
            errors.append(f"lane_missing_artifact_types:{lane.lane_id}")
        if not _safe_output_path(lane.default_output_dir):
            errors.append(f"unsafe_output_dir:{lane.lane_id}:{lane.default_output_dir}")
        if not lane.verifier:
            errors.append(f"lane_missing_verifier:{lane.lane_id}")
        if not set(DEFAULT_BLOCKED_ACTIONS).issubset(set(lane.blocked_actions)):
            errors.append(f"lane_missing_blocked_actions:{lane.lane_id}")
        if lane.lane_id != "orchestrator" and "orchestrator" not in lane.handoff_targets:
            errors.append(f"specialist_without_orchestrator_return:{lane.lane_id}")
        if len(lane.handoff_targets) >= len(REQUIRED_LANES) - 1 and lane.lane_id != "orchestrator":
            errors.append(f"specialist_looks_like_all_to_all_handoff:{lane.lane_id}")
        toolset_text = " ".join(lane.allowed_toolsets).lower()
        for token in FORBIDDEN_TOOLSET_TOKENS:
            if token in toolset_text:
                errors.append(f"forbidden_toolset_token:{lane.lane_id}:{token}")
        if lane.risk_class.startswith("R3") and not lane.operator_gate_required:
            errors.append(f"external_provider_lane_without_gate:{lane.lane_id}")
        if lane.status == "provider_gated_contract" and not lane.operator_gate_required:
            errors.append(f"provider_gated_lane_without_operator_gate:{lane.lane_id}")

    contract_ids = [contract.contract_id for contract in contracts]
    duplicate_contracts = sorted(
        {contract_id for contract_id in contract_ids if contract_ids.count(contract_id) > 1}
    )
    for contract_id in duplicate_contracts:
        errors.append(f"duplicate_contract_id:{contract_id}")

    covered_types: dict[str, set[str]] = {lane_id: set() for lane_id in lane_ids}
    for contract in contracts:
        if contract.lane_id not in lanes_by_id:
            errors.append(f"contract_unknown_lane:{contract.contract_id}:{contract.lane_id}")
            continue
        lane = lanes_by_id[contract.lane_id]
        covered_types[contract.lane_id].add(contract.artifact_type)
        if contract.artifact_type not in lane.artifact_types:
            errors.append(f"contract_artifact_not_declared:{contract.contract_id}")
        if not _safe_output_path(contract.default_path_template):
            errors.append(f"unsafe_contract_path:{contract.contract_id}")
        if not set(REQUIRED_CONTRACT_METADATA).issubset(set(contract.required_metadata)):
            errors.append(f"contract_missing_required_metadata:{contract.contract_id}")
        if "verified" not in contract.final_status_values or "blocked" not in contract.final_status_values:
            errors.append(f"contract_missing_final_statuses:{contract.contract_id}")
        if not contract.required_verification:
            errors.append(f"contract_missing_verification:{contract.contract_id}")
        if lane.operator_gate_required and contract.gate_rule != "operator_go_required":
            errors.append(f"gated_lane_contract_without_gate_rule:{contract.contract_id}")

    for lane in lanes:
        missing_types = sorted(set(lane.artifact_types) - covered_types.get(lane.lane_id, set()))
        for artifact_type in missing_types:
            errors.append(f"lane_artifact_without_contract:{lane.lane_id}:{artifact_type}")

    if len(contracts) < len(lanes):
        warnings.append("contract_count_lower_than_lane_count")

    return SwarmValidation(
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def render_deliverable_swarm_markdown(
    lanes: Sequence[DeliverableLane],
    contracts: Sequence[DeliveryContract],
    validation: SwarmValidation,
) -> str:
    lines = [
        "# Deliverable Swarm Contract",
        "",
        "This is the safe local transfer of the OpenSwarm pattern: visible specialist lanes "
        "and explicit output contracts, without external runtime installation.",
        "",
        f"Valid: `{str(validation.valid).lower()}`",
        f"Errors: `{', '.join(validation.errors) if validation.errors else 'none'}`",
        f"Warnings: `{', '.join(validation.warnings) if validation.warnings else 'none'}`",
        "",
        "## Lane Matrix",
        "",
        "| Lane | Status | Risk | Gate | Default output | Verifier | Handoff targets |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for lane in lanes:
        lines.append(
            f"| `{lane.lane_id}` | `{lane.status}` | `{lane.risk_class}` | "
            f"{str(lane.operator_gate_required).lower()} | `{lane.default_output_dir}` | "
            f"`{lane.verifier}` | `{', '.join(lane.handoff_targets)}` |"
        )

    lines.extend(
        [
            "",
            "## Output Contracts",
            "",
            "| Contract | Lane | Artifact | Default path | Gate rule | Verification |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for contract in contracts:
        lines.append(
            f"| `{contract.contract_id}` | `{contract.lane_id}` | `{contract.artifact_type}` | "
            f"`{contract.default_path_template}` | `{contract.gate_rule}` | "
            f"`{', '.join(contract.required_verification)}` |"
        )

    lines.extend(
        [
            "",
            "## Hard Boundaries",
            "",
        ]
    )
    for action in DEFAULT_BLOCKED_ACTIONS:
        lines.append(f"- `{action}`")
    lines.extend(
        [
            "",
            "## Adoption Rule",
            "",
            "Use this as the first user-facing capability surface for LIONCOM/Vivi/OpenClaw. "
            "It may route work to existing local skills and verified artifact workflows, but it "
            "does not install OpenSwarm, Composio, system packages, or background agents.",
            "",
        ]
    )
    return "\n".join(lines)
