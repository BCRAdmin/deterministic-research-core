from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.alpha_shared.compiler import execute_historical_regression
from research_agent.alpha_shared.contracts import DocumentObservationIR, SharedBaseInputIR
from research_agent.alpha_shared.frozen_evidence import load_frozen_evidence
from research_agent.alpha_shared.runner import run_shared_case
from research_agent.alpha_shared.supplemental_semantics import build_supplemental_semantics
from research_agent.tests.test_rfc0011_r2_correction import (
    _canonical_base,
    _mini_evidence_zip,
    _supplemental,
)


def _positive() -> DocumentObservationIR:
    return DocumentObservationIR.create(
        source_document_sha256="6" * 64,
        locator_type="table_cell",
        locator="table:1:row:2:column:1",
        row_index_or_null=2,
        column_index_or_null=1,
        header_path=("Three Months Ended June 30, 2026",),
        reported_label="oil-equivalent production",
        raw_value_text="4,514",
        parsed_numeric_value_or_null="4514",
        reported_unit_text_or_null="KBOE_PER_DAY",
        reported_period_text_or_null="Three Months Ended June 30, 2026",
        reported_basis_text_or_null="consolidated",
        context_text="Oil-equivalent production 4,514 KBOE per day",
        numeric_role="MEASURE_VALUE",
        trusted_numeric=True,
    )


def _missing_unit() -> DocumentObservationIR:
    return DocumentObservationIR.create(
        source_document_sha256="7" * 64,
        locator_type="table_cell",
        locator="table:1:row:2:column:2",
        row_index_or_null=2,
        column_index_or_null=2,
        header_path=("Six Months Ended June 30, 2026",),
        reported_label="oil-equivalent production",
        raw_value_text="4,630",
        parsed_numeric_value_or_null="4630",
        reported_period_text_or_null="Six Months Ended June 30, 2026",
        reported_basis_text_or_null="consolidated",
        context_text="Oil-equivalent production 4,630",
        numeric_role="MEASURE_VALUE",
        trusted_numeric=True,
    )


def test_r3_base_input_binds_exact_snapshot_identity(tmp_path: Path):
    base = _canonical_base(tmp_path)
    assert base.request_sha256 == base.snapshot_ir.request_sha256
    assert base.acquisition_plan_sha256 == base.snapshot_ir.acquisition_plan_sha256
    assert base.source_snapshot_sha256 == base.snapshot_ir.snapshot_sha256


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("request_sha256", "a" * 64),
        ("acquisition_plan_sha256", "b" * 64),
        ("retrieval_receipt_set_sha256", "c" * 64),
        ("source_snapshot_sha256", "d" * 64),
    ],
)
def test_r3_base_input_rejects_caller_identity_substitution(tmp_path: Path, field: str, value: str):
    data = _canonical_base(tmp_path).model_dump(mode="json")
    data[field] = value
    with pytest.raises(ValidationError, match="exactly bind"):
        SharedBaseInputIR.model_validate(data)


def test_r3_complete_supplemental_enters_h3_then_h2():
    candidates, resolutions = build_supplemental_semantics(
        supplemental=_supplemental(_positive()),
        as_of_date="2026-08-27",
        filed_date="2026-08-01",
        archetype_profile_id="energy",
    )
    assert candidates[0]["status"] == "CANDIDATE"
    assert candidates[0]["h3_receipt"]["duration_role"] == "STANDALONE_QUARTER"
    assert resolutions[0]["status"] == "RESOLVED"
    assert len(resolutions[0]["evidence_ids"]) == 3


def test_r3_missing_unit_is_explicitly_rejected():
    candidates, resolutions = build_supplemental_semantics(
        supplemental=_supplemental(_missing_unit()),
        as_of_date="2026-08-27",
        filed_date="2026-08-01",
        archetype_profile_id="energy",
    )
    assert candidates[0]["status"] == "REJECTED"
    assert "UNIT_BINDING_MISSING" in candidates[0]["reason_codes"]
    assert resolutions[0]["status"] == "UNSUPPORTED"


def test_r3_real_runner_emits_exact_identity_and_verified_bundle(tmp_path: Path):
    base = _canonical_base(tmp_path)
    result = run_shared_case(
        base_input=base,
        supplemental_input=_supplemental(_positive(), _missing_unit()),
        archetype_profile_id="energy",
        output_root=tmp_path / "bundle",
        ledger_path=tmp_path / "ledger.jsonl",
        research_commit="a" * 40,
        research_tree="b" * 40,
        monotonic_counter=1001,
    )
    identity = result.compiled.manifest["compile_identity"]
    assert identity["compile_request_sha256"] == base.snapshot_ir.request_sha256
    assert identity["source_acquisition_sha256"] == base.snapshot_ir.acquisition_plan_sha256
    assert identity["retrieval_receipt_set_sha256"] == base.retrieval_receipt_set_sha256
    assert identity["source_snapshot_sha256"] == base.snapshot_ir.snapshot_sha256
    assert result.report["actual_function_called"] == "run_shared_case"
    assert result.report["bundle_verified"] is True
    assert result.report["network_calls"] == result.report["fixed24_queries"] == 0


def test_r3_runner_replay_is_byte_identical(tmp_path: Path):
    base = _canonical_base(tmp_path)
    inputs = _supplemental(_positive(), _missing_unit())
    values = []
    for suffix in ("one", "two"):
        result = run_shared_case(
            base_input=base,
            supplemental_input=inputs,
            archetype_profile_id="energy",
            output_root=tmp_path / f"bundle-{suffix}",
            ledger_path=tmp_path / f"ledger-{suffix}.jsonl",
            research_commit="a" * 40,
            research_tree="b" * 40,
            monotonic_counter=1002,
        )
        values.append(
            (
                (result.compiled.bundle_root / "BUNDLE_MANIFEST.json").read_bytes(),
                (result.compiled.bundle_root / "RECEIPT.json").read_bytes(),
            )
        )
    assert values[0] == values[1]


def test_r3_historical_adapter_never_claims_live_identity(tmp_path: Path):
    inventory = load_frozen_evidence(
        _mini_evidence_zip(tmp_path / "historical.zip"),
        ticker="TST",
        as_of_date="2026-08-27",
    )
    report = execute_historical_regression(inventory)
    assert report["provenance_mode"] == "HISTORICAL_EVIDENCE_ADAPTER"
    assert report["canonical_live_compile_identity"] is False
    assert report["native_compile_identity"] is None
    assert report["network_call_count"] == 0


def test_r3_bundle_extension_keeps_supplemental_out_of_native_identity(tmp_path: Path):
    base = _canonical_base(tmp_path)
    supplemental = _supplemental(_positive())
    result = run_shared_case(
        base_input=base,
        supplemental_input=supplemental,
        archetype_profile_id="energy",
        output_root=tmp_path / "bundle",
        ledger_path=tmp_path / "ledger.jsonl",
        research_commit="a" * 40,
        research_tree="b" * 40,
        monotonic_counter=1003,
    )
    identity_values = set(result.compiled.manifest["compile_identity"].values())
    assert supplemental.supplemental_evidence_set_sha256 not in identity_values
    extension = result.compiled.manifest["extensions"]["rfc0011_shared_successor_r3"]
    assert (
        extension["supplemental_evidence_set_sha256"]
        == supplemental.supplemental_evidence_set_sha256
    )
    evidence = json.loads(
        (result.compiled.bundle_root / "artifacts/evidence_graph.json").read_text()
    )
    assert evidence["supplemental_candidate_receipts"]
