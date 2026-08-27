from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from research_agent.alpha_shared.compiler import (
    compile_shared_successor,
    execute_shared_semantics,
    future_batch_dry_run_plan,
)
from research_agent.alpha_shared.concept_registry import CONCEPT_REGISTRY_SHA256, concept_record
from research_agent.alpha_shared.document_normalizer import (
    classify_numeric_role,
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.frozen_evidence import load_frozen_evidence
from research_agent.alpha_shared.metric_resolver import MetricCandidate, resolve_metric
from research_agent.alpha_shared.contracts import SharedBaseInputIR, SupplementalCompileInputIR
from research_agent.productization_v2.native_trust import verify_native_bundle_v2
from research_agent.semantic_compiler.source_frontend.contracts import (
    RetrievalReceiptIR,
    SourceArtifactIR,
    SourceDispositionIR,
    SourceSnapshotIR,
)

ROOT = Path(__file__).resolve().parents[2]
FALSE_FIXTURES = json.loads(
    (ROOT / "research_agent/alpha_shared/config/r2_real_false_positive_fixtures.json").read_text()
)


def _document(text: str, media_type: str = "text/plain"):
    return normalize_document(
        text.encode(),
        document_id="r2",
        accession_number="1",
        report_date="2026-06-30",
        filing_date="2026-08-01",
        document_name="fixture.txt",
        media_type=media_type,
    )


def _candidate(concept: str, metric: str, **updates: object) -> MetricCandidate:
    semantic = concept_record(metric, concept)
    values = {
        "candidate_id": f"candidate.{concept}",
        "concept_or_label": concept,
        "source_kind": "frozen_alpha_evidence",
        "period_type": "INSTANT",
        "period_role": "CURRENT_PRIMARY",
        "freshness_status": "CURRENT",
        "unit": "USD",
        "evidence_ids": ("evidence.actual",),
        "semantic_metric_id": metric,
        "semantic_role": semantic["semantic_role"] if semantic else None,
        "aggregation_role": semantic["aggregation_role"] if semantic else None,
        "period_receipt_sha256": "1" * 64,
        "inventory_sha256": "2" * 64,
        "numeric_value": "100",
        "trusted_numeric": True,
    }
    values.update(updates)
    return MetricCandidate(**values)


def _mini_evidence_zip(path: Path, ticker: str = "TST") -> Path:
    report = {
        "contract_id": "fixture.actual_facts",
        "facts": [
            {
                "fact_id": "fact.cash",
                "concept": "CashAndCashEquivalentsAtCarryingValue",
                "semantic_metric_id": "cash_and_equivalents",
                "value": 42,
                "unit": "USD",
                "period_end": "2026-06-30",
                "filed_date": "2026-08-01",
                "form": "10-Q",
            },
            {
                "fact_id": "fact.capex",
                "concept": "PaymentsToAcquirePropertyPlantAndEquipment",
                "semantic_metric_id": "capital_expenditure",
                "value": 7,
                "unit": "USD",
                "period_start": "2026-01-01",
                "period_end": "2026-06-30",
                "filed_date": "2026-08-01",
                "form": "10-Q",
            },
        ],
        "snapshot_sha256": "3" * 64,
        "ticker": ticker,
    }
    report_bytes = json.dumps(report, sort_keys=True).encode()
    manifest = {
        "files": [{"path": "ACTUAL_FACTS.json", "sha256": hashlib.sha256(report_bytes).hexdigest()}]
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ACTUAL_FACTS.json", report_bytes)
        archive.writestr("MANIFEST.json", json.dumps(manifest, sort_keys=True))
    return path


def _canonical_base(tmp_path: Path, ticker: str = "TST") -> SharedBaseInputIR:
    payload = {
        "facts": {
            "us-gaap": {
                "CashAndCashEquivalentsAtCarryingValue": {
                    "label": "Cash",
                    "units": {
                        "USD": [
                            {
                                "val": 42,
                                "end": "2026-06-30",
                                "filed": "2026-08-01",
                                "form": "10-Q",
                            }
                        ]
                    },
                }
            }
        }
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    snapshot_root = tmp_path / "snapshot"
    relative = f"sources/{digest[:2]}/{digest}.json"
    target = snapshot_root / relative
    target.parent.mkdir(parents=True)
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
        ticker=ticker,
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
    return SharedBaseInputIR.from_snapshot(snapshot=snapshot, snapshot_root=snapshot_root)


def _supplemental(*observations):
    return SupplementalCompileInputIR.create(
        supplemental_policy_sha256="3" * 64,
        discovery_set_sha256="4" * 64,
        supplemental_evidence_set_sha256="5" * 64,
        observations=tuple(observations),
    )


def test_r2_obs_001_short_alias_respects_token_boundary():
    observations = discover_observations(
        _document("Represents minimum requirements. Refer to Note 21."),
        {"net_interest_margin": ("nim",)},
    )
    assert observations == ()


@pytest.mark.parametrize(
    "fixture", FALSE_FIXTURES["fixtures"], ids=lambda item: f"{item['ticker']}-{item['raw_value']}"
)
def test_r2_obs_002_010_real_r1_false_positives_are_untrusted(fixture: dict[str, str]):
    observations = discover_observations(
        _document(fixture["text"]), {fixture["metric_id"]: (fixture["label"],)}
    )
    if fixture["ticker"] == "JPM":
        assert observations == ()
        return
    assert observations
    match = next(item for item in observations if fixture["raw_value"] in item.raw_value_text)
    assert match.trusted_numeric is False
    assert match.numeric_role == fixture["expected_numeric_role"]


def test_r2_obs_005_multi_period_table_keeps_separate_cells():
    html = "<table><tr><th>Metric</th><th>Q1 2026</th><th>Q2 2026</th></tr><tr><td>Net interest margin</td><td>2.1%</td><td>2.3%</td></tr></table>"
    observations = discover_observations(
        _document(html, "text/html"), {"net_interest_margin": ("net interest margin",)}
    )
    assert len(observations) == 2
    assert {item.header_path for item in observations} == {("Q1 2026",), ("Q2 2026",)}
    assert all(item.trusted_numeric and item.locator_type == "table_cell" for item in observations)


def test_r2_obs_006_table_value_retains_coordinates_and_header():
    html = "<table><tr><th>Metric</th><th>Current</th></tr><tr><td>Core FFO</td><td>$12.5</td></tr></table>"
    item = discover_observations(_document(html, "text/html"), {"adjusted_ffo": ("core ffo",)})[0]
    assert (item.row_index_or_null, item.column_index_or_null, item.header_path) == (
        1,
        1,
        ("Current",),
    )
    assert item.numeric_role == "MEASURE_VALUE" and item.trusted_numeric


def test_r2_obs_numeric_role_helpers_cover_note_period_and_footnote():
    assert classify_numeric_role(context="Note 21", token="21", label="nim") == "NOTE_REFERENCE"
    assert (
        classify_numeric_role(context="next 12 months", token="12", label="rpo") == "PERIOD_VALUE"
    )
    assert (
        classify_numeric_role(context="Production (1)", token="1", label="production")
        == "FOOTNOTE_MARKER"
    )


def test_r2_sem_001_bank_net_revenue_rejects_interest_component():
    candidate = _candidate(
        "InterestIncomeExpenseNonoperatingNet",
        "net_revenue",
        period_type="DURATION",
        period_role="CURRENT_YTD",
    )
    receipt = resolve_metric("net_revenue", (candidate,))
    assert (
        receipt.status == "UNSUPPORTED"
        and "SEMANTIC_ROLE_COMPONENT_ONLY" in receipt.rejected_candidates[0].reason_codes
    )


def test_r2_sem_001_bank_does_not_relabel_generic_revenues_as_net_revenue():
    candidate = _candidate(
        "Revenues",
        "net_revenue",
        period_type="DURATION",
        period_role="CURRENT_YTD",
        archetype_profile_id="bank",
    )
    receipt = resolve_metric("net_revenue", (candidate,))
    assert receipt.status == "UNSUPPORTED"
    assert "ARCHETYPE_PROFILE_INCOMPATIBLE" in receipt.rejected_candidates[0].reason_codes


def test_r2_sem_002_fcf_rejects_incurred_not_paid_capex():
    candidate = _candidate(
        "CapitalExpendituresIncurredButNotYetPaid",
        "capital_expenditure",
        period_type="DURATION",
        period_role="CURRENT_YTD",
        formula_use_or_null="free_cash_flow",
    )
    receipt = resolve_metric("capital_expenditure", (candidate,))
    assert (
        receipt.status == "UNSUPPORTED"
        and "FORMULA_USE_INELIGIBLE" in receipt.rejected_candidates[0].reason_codes
    )


def test_r2_sem_003_restricted_cash_is_not_unrestricted_cash():
    candidate = _candidate(
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "cash_and_equivalents",
        formula_use_or_null="net_debt",
    )
    assert resolve_metric("cash_and_equivalents", (candidate,)).status == "UNSUPPORTED"


def test_r2_sem_004_current_debt_component_is_not_long_term_total():
    candidate = _candidate("LongTermDebtCurrent", "long_term_debt")
    assert resolve_metric("long_term_debt", (candidate,)).status == "UNSUPPORTED"


def test_r2_evid_actual_inventory_binds_zip_entry_and_fact(tmp_path: Path):
    inventory = load_frozen_evidence(
        _mini_evidence_zip(tmp_path / "evidence.zip"), ticker="TST", as_of_date="2026-08-27"
    )
    assert len(inventory.facts) == 2
    assert (
        inventory.inspected_entry_sha256s["ACTUAL_FACTS.json"]
        == inventory.facts[0].source_entry_sha256
    )
    assert len(inventory.inventory_sha256) == 64


def test_r2_evid_h3_then_h2_use_actual_inventory(tmp_path: Path):
    inventory = load_frozen_evidence(
        _mini_evidence_zip(tmp_path / "evidence.zip"), ticker="TST", as_of_date="2026-08-27"
    )
    periods, resolutions = execute_shared_semantics(inventory)
    assert periods and all(
        item["inventory_sha256"] == inventory.inventory_sha256 for item in periods
    )
    assert all(item["inventory_sha256"] == inventory.inventory_sha256 for item in resolutions)
    assert (
        next(item for item in resolutions if item["metric_id"] == "capital_expenditure")[
            "actual_candidate_count"
        ]
        == 1
    )


def test_r2_int_shared_compiler_emits_and_verifies_native_bundle(tmp_path: Path):
    base = _canonical_base(tmp_path)
    result = compile_shared_successor(
        base_input=base,
        archetype_profile_id="generic",
        supplemental_input=_supplemental(),
        output_root=tmp_path / "bundle",
        ledger_path=tmp_path / "operations.jsonl",
        research_commit="a" * 40,
        research_tree="b" * 40,
        monotonic_counter=991,
    )
    assert result.manifest["contract_version"] == 2
    assert result.verification["status"] == "PASS"
    assert (
        verify_native_bundle_v2(
            result.bundle_root, receipt=result.receipt, now_utc="2026-08-27T23:30:00Z"
        )["status"]
        == "PASS"
    )
    stages = [item["stage"] for item in result.ledger_report["events"]]
    assert (
        "h3_period_freshness" in stages
        and "h2_semantic_resolution" in stages
        and "bundle_v2_receipt_verify" in stages
    )


def test_r2_int_untrusted_supplemental_never_enters_metric_truth(tmp_path: Path):
    base = _canonical_base(tmp_path)
    from research_agent.alpha_shared.contracts import DocumentObservationIR

    observation = DocumentObservationIR.create(
        source_document_sha256="4" * 64,
        locator_type="text_span",
        locator="block:0",
        reported_label="cash",
        raw_value_text="999",
        parsed_numeric_value_or_null="999",
        context_text="cash 999",
        ambiguity_codes=("TEXT_SPAN_UNTRUSTED_BY_DEFAULT",),
        trusted_numeric=False,
    )
    result = compile_shared_successor(
        base_input=base,
        archetype_profile_id="generic",
        supplemental_input=_supplemental(observation),
        output_root=tmp_path / "bundle",
        ledger_path=tmp_path / "operations.jsonl",
        research_commit="a" * 40,
        research_tree="b" * 40,
        monotonic_counter=992,
    )
    report = json.loads((result.bundle_root / "artifacts/verification_report.json").read_text())
    assert report["untrusted_supplemental_count"] == 1
    assert all(
        item.get("value") != "999"
        for item in json.loads((result.bundle_root / "artifacts/metrics.json").read_text())[
            "metrics"
        ]
    )


def test_r2_int_future_batch_dry_run_imports_shared_compiler_without_query():
    plan = future_batch_dry_run_plan()
    assert plan["network_call_count"] == plan["fixed24_query_count"] == 0
    assert plan["fixed24_batch_authorized"] is False
    assert plan["actual_runner"].endswith("run_shared_case")
    assert plan["status"] == "PLAN_ONLY"
    assert len(CONCEPT_REGISTRY_SHA256) == 64
