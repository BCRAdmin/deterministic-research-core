from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from research_agent.alpha_shared import compiler as shared_compiler
from research_agent.alpha_shared.archetype_profiles import (
    FREEZE_SHA256S,
    REQUIRED_REPORT_SECTIONS,
    archetype_profile_registry,
    load_archetype_profile,
)
from research_agent.alpha_shared.contracts import SharedBaseInputIR
from research_agent.alpha_shared.internal_report import (
    build_internal_alpha_report,
    compute_batch_threshold_metrics,
)
from research_agent.alpha_shared.execution_authority import (
    BatchExecutionAuthorityIR,
    BatchExecutionCaseIR,
    RuntimeIdentityIR,
    authorize_case_before_network,
)
from research_agent.alpha_shared.raw_inventory import (
    build_source_snapshot_fact_inventory,
)
from research_agent.alpha_shared.runner import (
    replay_canonical_alpha_case,
    run_canonical_alpha_case,
)
from research_agent.semantic_compiler.source_frontend.contracts import (
    RetrievalReceiptIR,
    SourceArtifactIR,
    SourceDispositionIR,
    SourceSnapshotIR,
)
from research_agent.tests.test_rfc0011_r2_correction import (
    _canonical_base,
    _supplemental,
)
from research_agent.tests.test_rfc0011_r3_correction import _positive


def _raw_base(tmp_path: Path) -> SharedBaseInputIR:
    observations = [
        {
            "val": 30,
            "start": "2026-04-01",
            "end": "2026-06-30",
            "filed": "2026-08-01",
            "form": "10-Q",
            "accn": "q2",
        },
        {
            "val": 50,
            "start": "2026-01-01",
            "end": "2026-06-30",
            "filed": "2026-08-01",
            "form": "10-Q",
            "accn": "h1",
        },
        {
            "val": 70,
            "start": "2026-04-01",
            "end": "2026-06-30",
            "filed": "2026-08-28",
            "form": "10-Q",
            "accn": "future",
        },
    ]
    payload = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "label": "Revenue",
                    "units": {"USD": observations},
                },
                "CashAndCashEquivalentsAtCarryingValue": {
                    "label": "Cash",
                    "units": {
                        "USD": [
                            {
                                "val": 9,
                                "end": "2026-06-30",
                                "filed": "2026-08-01",
                                "form": "10-Q",
                            }
                        ]
                    },
                },
            }
        }
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    root = tmp_path / "snapshot"
    relative = f"sources/{digest[:2]}/{digest}.json"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    artifact = SourceArtifactIR(
        snapshot_id=f"snapshot.{digest}",
        path=relative,
        sha256=digest,
        bytes=len(raw),
        media_type="application/json",
    )
    receipt = RetrievalReceiptIR(
        receipt_id=f"receipt.{digest}",
        acquisition_id="source.sec",
        source_id="SEC_COMPANYFACTS_TEST",
        source_type="sec_filing",
        provider_id="sec",
        original_locator="fixture://companyfacts",
        media_type="application/json",
        payload_sha256=digest,
        payload_bytes=len(raw),
        retrieved_at="2026-08-01T12:00:00Z",
        available_at="2026-08-01T12:00:00Z",
        filing_date="2026-08-01",
        transport="offline_fixture",
    )
    snapshot = SourceSnapshotIR.create(
        request_sha256="1" * 64,
        acquisition_plan_sha256="2" * 64,
        ticker="XOM",
        as_of_date="2026-08-27",
        artifacts=(artifact,),
        retrieval_receipts=(receipt,),
        source_dispositions=(
            SourceDispositionIR(
                source_id=receipt.source_id,
                source_type=receipt.source_type,
                provider_id=receipt.provider_id,
                receipt_id=receipt.receipt_id,
                snapshot_ids=(artifact.snapshot_id,),
                disposition="material_evidence",
            ),
        ),
    )
    return SharedBaseInputIR.from_snapshot(snapshot=snapshot, snapshot_root=root)


def _raw_base_with_market(tmp_path: Path) -> SharedBaseInputIR:
    base = _raw_base(tmp_path)
    payload = [{"date": "2026-08-26", "close": 158.19}]
    raw = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    root = Path(base.snapshot_root)
    relative = f"sources/{digest[:2]}/{digest}.json"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    artifact = SourceArtifactIR(
        snapshot_id=f"snapshot.{digest}",
        path=relative,
        sha256=digest,
        bytes=len(raw),
        media_type="application/json",
    )
    receipt = RetrievalReceiptIR(
        receipt_id=f"receipt.{digest}",
        acquisition_id="source.nasdaq",
        source_id="NASDAQ_OHLCV_XOM",
        source_type="exchange_ohlcv",
        provider_id="nasdaq",
        original_locator="fixture://market",
        media_type="application/json",
        payload_sha256=digest,
        payload_bytes=len(raw),
        retrieved_at="2026-08-27T12:00:00Z",
        available_at="2026-08-27T12:00:00Z",
        transport="offline_fixture",
    )
    prior = base.snapshot_ir
    snapshot = SourceSnapshotIR.create(
        request_sha256=prior.request_sha256,
        acquisition_plan_sha256=prior.acquisition_plan_sha256,
        ticker=prior.ticker,
        as_of_date=prior.as_of_date,
        artifacts=(*prior.artifacts, artifact),
        retrieval_receipts=(*prior.retrieval_receipts, receipt),
        source_dispositions=(
            *prior.source_dispositions,
            SourceDispositionIR(
                source_id=receipt.source_id,
                source_type=receipt.source_type,
                provider_id=receipt.provider_id,
                receipt_id=receipt.receipt_id,
                snapshot_ids=(artifact.snapshot_id,),
                disposition="material_evidence",
            ),
        ),
    )
    return SharedBaseInputIR.from_snapshot(snapshot=snapshot, snapshot_root=root)


def test_r4_raw_inventory_is_lossless_period_aware_and_deterministic(tmp_path: Path):
    inventory = build_source_snapshot_fact_inventory(_raw_base(tmp_path))
    revenue = [
        item
        for item in inventory.candidates
        if item.concept == "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]
    assert {item.preliminary_duration_role for item in revenue} == {
        "STANDALONE_QUARTER",
        "YEAR_TO_DATE",
    }
    assert all(item.start_or_null for item in revenue)
    assert len({item.candidate_id for item in revenue}) == 2
    assert inventory == build_source_snapshot_fact_inventory(_raw_base(tmp_path))
    assert any("FILED_AFTER_AS_OF" in item.reason_codes for item in inventory.exclusions)


def test_r4_instant_and_duration_h3_basis_are_not_interchangeable(tmp_path: Path):
    inventory = build_source_snapshot_fact_inventory(_raw_base(tmp_path))
    cash = next(item for item in inventory.candidates if item.concept.startswith("CashAnd"))
    revenue = next(item for item in inventory.candidates if item.concept.startswith("Revenue"))
    report = build_internal_alpha_report(inventory, load_archetype_profile("saas"))
    periods = {item["candidate_id"]: item for item in report.period_receipts}
    assert cash.start_or_null is None and periods[cash.candidate_id]["period_type"] == "INSTANT"
    assert revenue.start_or_null is not None
    assert periods[revenue.candidate_id]["period_type"] == "DURATION"


def test_r4_market_price_remains_a_separate_instant_candidate_family(tmp_path: Path):
    inventory = build_source_snapshot_fact_inventory(_raw_base_with_market(tmp_path))
    market = [item for item in inventory.candidates if item.source_kind == "market_price"]
    assert len(market) == 1
    assert market[0].concept == "LatestMarketClose"
    assert market[0].start_or_null is None
    assert market[0].preliminary_duration_role == "INSTANT"
    assert market[0].provider_id == "nasdaq"


def test_r4_shared_compiler_has_no_latest_companyfacts_projection():
    assert "_latest_company_facts" not in inspect.getsource(shared_compiler)


@pytest.mark.parametrize("profile_id", ("saas", "reit", "bank", "energy"))
def test_r4_profile_adapter_binds_exact_development_freeze(profile_id: str):
    profile = load_archetype_profile(profile_id)
    assert profile.profile_freeze_sha256 == FREEZE_SHA256S[profile_id]
    assert profile.ticker_specific_rules is False
    assert profile.required_report_sections == REQUIRED_REPORT_SECTIONS


def test_r4_profile_registry_contains_only_four_frozen_archetypes():
    registry = archetype_profile_registry()
    assert [item["archetype_profile_id"] for item in registry["profiles"]] == [
        "saas",
        "reit",
        "bank",
        "energy",
    ]
    assert registry["ticker_specific_rules"] is False


def test_r4_internal_report_coverage_lineage_and_sections_are_honest(tmp_path: Path):
    inventory = build_source_snapshot_fact_inventory(_raw_base(tmp_path))
    result = build_internal_alpha_report(inventory, load_archetype_profile("saas"))
    report = result.report
    assert report.report_completeness["required_section_completeness_percent"] == 100
    assert report.evidence_lineage["surfaced_fact_lineage_rate_percent"] == 100
    assert report.source_coverage["covered_core_metric_count"] == len(report.core_metrics)
    assert not set(report.important_unsupported_metrics).intersection(
        item.metric_id for item in report.core_metrics
    )


@pytest.mark.parametrize("profile_id", ("saas", "reit", "bank", "energy"))
def test_r4_canonical_local_fixture_uses_same_runner_for_every_archetype(
    tmp_path: Path, profile_id: str
):
    result = replay_canonical_alpha_case(
        base_input=_canonical_base(tmp_path / profile_id),
        supplemental_input=_supplemental(_positive()),
        archetype_profile_id=profile_id,
        output_root=tmp_path / f"bundle-{profile_id}",
        ledger_path=tmp_path / f"ledger-{profile_id}.jsonl",
        research_commit="a" * 40,
        research_tree="b" * 40,
        monotonic_counter=2000,
    )
    assert result.report["actual_function_called"] == "run_canonical_alpha_case"
    assert result.report["bundle_verified"] is True
    assert result.report["replay_network_call_count"] == 0
    assert result.compiled.archetype_profile.archetype_profile_id == profile_id


def test_r4_verified_live_receipts_populate_h4_provider_telemetry(tmp_path: Path):
    runtime = RuntimeIdentityIR(
        research_commit="a" * 40,
        research_tree="b" * 40,
        product_commit="c" * 40,
        product_tree="d" * 40,
        as_of_date="2026-08-27",
    )
    authority = BatchExecutionAuthorityIR.create(
        authority_kind="DEVELOPMENT_VALIDATION",
        as_of_date=runtime.as_of_date,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=None,
        fixed_company_list_sha256=None,
        threshold_sha256=None,
        ordered_cases=(
            BatchExecutionCaseIR(
                sequence=1,
                ticker="XOM",
                company_name="Exxon Mobil Corporation",
                archetype_profile_id="energy",
            ),
        ),
        network_live_authorized=True,
    )
    receipt = authorize_case_before_network(
        ticker="XOM",
        archetype_profile_id="energy",
        sequence=1,
        authority=authority,
        runtime_identity=runtime,
    )
    result = run_canonical_alpha_case(
        base_input=_canonical_base(tmp_path, ticker="XOM"),
        supplemental_input=_supplemental(_positive()),
        archetype_profile_id="energy",
        output_root=tmp_path / "bundle",
        ledger_path=tmp_path / "ledger.jsonl",
        research_commit="a" * 40,
        research_tree="b" * 40,
        monotonic_counter=2001,
        acquisition_mode="verified_live_capture",
        authorization_receipt=receipt,
    )
    assert result.report["live_network_call_count"] == 1
    assert result.report["live_capture_bytes"] > 0
    stages = {item["stage"] for item in result.compiled.ledger_report["events"]}
    assert {"rfc0011.discovery", "rfc0011.child_capture.bound", "rfc0011.normalize"} <= stages
    aggregate = result.compiled.ledger_report["aggregate"]
    assert aggregate["core_metric_coverage"] == result.report["core_metric_coverage_percent"]
    assert aggregate["report_section_completeness"] == 100


def test_r4_replay_is_semantically_identical_and_provider_silent(tmp_path: Path):
    base = _canonical_base(tmp_path / "source", ticker="XOM")
    supplemental = _supplemental(_positive())
    results = []
    for suffix in ("one", "two"):
        results.append(
            replay_canonical_alpha_case(
                base_input=base,
                supplemental_input=supplemental,
                archetype_profile_id="energy",
                output_root=tmp_path / f"bundle-{suffix}",
                ledger_path=tmp_path / f"ledger-{suffix}.jsonl",
                research_commit="a" * 40,
                research_tree="b" * 40,
                monotonic_counter=2002,
            )
        )
    assert results[0].compiled.manifest == results[1].compiled.manifest
    assert results[0].compiled.receipt == results[1].compiled.receipt
    assert results[0].compiled.internal_report == results[1].compiled.internal_report
    assert all(item.report["replay_network_call_count"] == 0 for item in results)


def test_r4_batch_threshold_metrics_are_computable_without_fixed24(tmp_path: Path):
    inventory = build_source_snapshot_fact_inventory(_raw_base(tmp_path))
    reports = tuple(
        build_internal_alpha_report(inventory, load_archetype_profile(profile)).report
        for profile in ("saas", "reit", "bank", "energy")
    )
    metrics = compute_batch_threshold_metrics(reports)
    assert metrics["report_count"] == 4
    assert len(metrics["per_archetype_complete_reports"]) == 4
    assert metrics["minimum_required_section_completeness"] == 100
    assert metrics["minimum_surfaced_fact_lineage"] == 100
    assert metrics["offline_replay_identity_for_completed_runs_percent"] == 100
    assert metrics["manual_intervention_count"] == 0
    assert metrics["provider_calls_during_replay"] == 0
    assert metrics["P0_count"] == metrics["P1_count"] == 0
    assert metrics["ticker_specific_or_issuer_specific_semantic_patches"] == 0
    assert metrics["fixed24_run_count"] == 0
