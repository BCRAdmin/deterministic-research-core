from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.ba12_live_source.ba3_bridge import (
    LiveBridgeResult,
    bridge_capture_set_to_ba3,
)
from research_agent.ba12_live_source.capture_store import ContentAddressedCaptureStore
from research_agent.ba12_live_source.contracts import (
    LiveCaptureBinding,
    LiveCaptureDisposition,
    LiveCaptureError,
    LiveCaptureSet,
    LiveRetrievalReceipt,
)
from research_agent.ba12_live_source.live_receipt import (
    LiveCaptureExecutor,
    ProviderResponse,
    adapter_implementation_sha256,
)
from research_agent.ba12_live_source.recovery import recover_after_capture, recover_bridge
from research_agent.ba12_live_source.verifier import (
    verify_authority_boundary,
    verify_live_bridge,
)
from research_agent.semantic_compiler.source_frontend.contracts import RetrievalReceiptIR
from research_agent.semantic_compiler.source_frontend.planner import (
    build_compile_request,
    plan_source_acquisition,
)

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
BA3_CONTRACT = ROOT / "research_agent/semantic_compiler/source_frontend/contracts.py"
BA3_CONTRACT_SHA256 = "c37dd7847905f9113e5b50af9ba669cebf06f1520c2099de65cb5e4ce16fda2b"
SEMANTIC_WAVE_LOCK = "62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9"
RFC0009_FREEZE = "e9c9e6e5e5573961207babd66d7c981504d118ed4d14e87f7d6a8ca4180904b9"
STAGED_AT = "2026-08-24T18:00:00+00:00"
FETCHED_AT = "2026-08-24T17:00:00+00:00"
AVAILABLE_AT = "2026-08-24T16:00:00+00:00"


def _resolution(jurisdiction: str) -> dict[str, object]:
    if jurisdiction == "HU":
        return {
            "status": "supported",
            "runtimeReady": True,
            "inputKind": "isin",
            "input": "HU0000153937",
            "ticker": "MOL",
            "companyName": "MOL Plc",
            "exchange": "Budapest Stock Exchange",
            "exchangeCode": "BSE",
            "jurisdiction": "HU",
            "isin": "HU0000153937",
            "source": "fixture",
        }
    return {
        "status": "supported",
        "runtimeReady": True,
        "inputKind": "ticker",
        "input": "AAPL",
        "ticker": "AAPL",
        "companyName": "Apple Inc.",
        "exchange": "Nasdaq",
        "exchangeCode": "XNAS",
        "jurisdiction": "US",
        "isin": "US0378331005",
        "source": "fixture",
    }


def _request_plan(provider: str = "nasdaq"):
    if provider == "bse":
        request = build_compile_request(
            _resolution("HU"),
            as_of_date="2026-08-24",
            allowed_provider_ids=("bse",),
            network_mode="live_acquisition",
        )
        return request, plan_source_acquisition(request)
    approved = ("massive",) if provider == "massive" else ()
    request = build_compile_request(
        _resolution("US"),
        as_of_date="2026-08-24",
        allowed_provider_ids=("massive", "sec") if provider == "massive" else ("nasdaq", "sec"),
        approved_paid_provider_ids=approved,
        available_configuration_ids=("ROOM16_SEC_USER_AGENT",),
        network_mode="live_acquisition",
    )
    return request, plan_source_acquisition(request, price_provider_id=provider)


def _response(provider: str, *, payload: bytes | None = None, source_id: str | None = None):
    source_type = "sec_filing" if provider == "sec" else "exchange_ohlcv"
    body = payload if payload is not None else f'{{"provider":"{provider}","value":1}}'.encode()
    paid = provider == "massive"
    return ProviderResponse(
        provider_id=provider,
        source_id=source_id or f"RFC0010_{provider.upper()}_SOURCE",
        source_type=source_type,
        original_locator=f"https://fixture.invalid/{provider}/source",
        final_locator=f"https://fixture.invalid/{provider}/source?final=1",
        status="200",
        media_type="application/json",
        payload=body,
        fetched_at_utc=FETCHED_AT,
        available_at_utc=AVAILABLE_AT,
        published_at_utc_or_null=AVAILABLE_AT,
        variable_cost_incurred=paid,
        variable_cost_amount_or_null="0.01" if paid else None,
        variable_cost_currency_or_null="USD" if paid else None,
    )


def _capture_all(tmp_path: Path, provider: str = "nasdaq"):
    request, plan = _request_plan(provider)
    executor = LiveCaptureExecutor(tmp_path / "live")
    records = tuple(
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id=item.acquisition_id,
            attempt_id=f"attempt.{item.provider_id}.1",
            adapter=lambda provider_id=item.provider_id: _response(provider_id),
        )
        for item in plan.acquisitions
    )
    return request, plan, executor, records


def _bridge(tmp_path: Path, provider: str = "nasdaq"):
    request, plan, executor, records = _capture_all(tmp_path, provider)
    result = bridge_capture_set_to_ba3(
        request=request,
        plan=plan,
        records=records,
        capture_store_root=executor.capture_store.root,
        snapshot_root=tmp_path / "snapshot",
        staged_at_utc=STAGED_AT,
    )
    return request, plan, executor, records, result


def _record_for(records, provider: str):
    return next(item for item in records if item.receipt.provider_id == provider)


def test_rfc10_t_001_ba3_contract_file_byte_hash_unchanged():
    assert hashlib.sha256(BA3_CONTRACT.read_bytes()).hexdigest() == BA3_CONTRACT_SHA256


def test_rfc10_t_002_semantic_wave_v1_freeze_verifier_unchanged():
    result = subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "scripts/ops/verify_semantic_compiler_wave_freeze.py"),
            "--product-repo",
            str(PRODUCT),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["version_lock_sha256"] == SEMANTIC_WAVE_LOCK


def test_rfc10_t_003_rfc0009_freeze_verifier_unchanged():
    result = subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "scripts/ops/verify_rfc0009_native_trust_freeze.py"),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert json.loads(result.stdout)["freeze_sha256"] == RFC0009_FREEZE


def test_rfc10_t_004_live_receipt_transport_is_live_acquisition(tmp_path: Path):
    *_, records = _capture_all(tmp_path, "bse")
    assert records[0].receipt.transport == "live_acquisition"


def test_rfc10_t_005_live_receipt_blocks_offline_replay_label(tmp_path: Path):
    *_, records = _capture_all(tmp_path, "bse")
    payload = records[0].receipt.model_dump(mode="json")
    payload["transport"] = "offline_replay"
    with pytest.raises(ValidationError):
        LiveRetrievalReceipt.model_validate(payload)


def test_rfc10_t_006_network_bytes_persist_before_parser_use(tmp_path: Path):
    *_, executor, records = _capture_all(tmp_path, "bse")
    record = records[0]
    assert executor.capture_store.read_verified(record.artifact) == _response("bse").payload
    assert not hasattr(record, "payload")


def test_rfc10_t_007_parser_cannot_receive_raw_network_response_directly():
    source = inspect.getsource(LiveCaptureExecutor.capture)
    assert source.index("capture_store.persist") < source.index("finalize_receipt")
    assert "return LiveCaptureRecord" not in source


def test_rfc10_t_008_readback_hash_or_size_mismatch_blocks(tmp_path: Path):
    store = ContentAddressedCaptureStore(tmp_path / "store")
    artifact = store.persist(b"trusted", media_type="text/plain", write_completed_at_utc=FETCHED_AT)
    target = store.root / artifact.content_addressed_relative_path
    target.chmod(0o644)
    target.write_bytes(b"tampered")
    with pytest.raises(LiveCaptureError, match="LIVE_CAPTURE_READBACK_MISMATCH"):
        store.read_verified(artifact)


def test_rfc10_t_009_path_traversal_or_symlink_escape_blocks(tmp_path: Path):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(LiveCaptureError, match="LIVE_CAPTURE_ROOT_SYMLINK"):
        ContentAddressedCaptureStore(link)


def test_rfc10_t_010_allowed_free_provider_live_capture(tmp_path: Path):
    *_, records = _capture_all(tmp_path, "bse")
    assert records[0].receipt.provider_id == "bse"
    assert not records[0].receipt.variable_cost_incurred


def test_rfc10_t_011_approved_paid_provider_has_cost_receipt(tmp_path: Path):
    *_, records = _capture_all(tmp_path, "massive")
    receipt = _record_for(records, "massive").receipt
    assert receipt.variable_cost_incurred and receipt.paid_provider_approval_bound
    assert receipt.variable_cost_amount_or_null == "0.01"


def test_rfc10_t_012_paid_provider_without_approval_blocks(tmp_path: Path):
    approved_request, approved_plan = _request_plan("massive")
    policy = approved_request.policy.model_copy(update={"approved_paid_provider_ids": ()})
    request = approved_request.__class__.create(
        instrument=approved_request.instrument,
        as_of_date=approved_request.as_of_date,
        policy=policy,
        market_capability_registry_sha256=approved_request.market_capability_registry_sha256,
    )
    plan = approved_plan.__class__.create(
        request_sha256=request.request_sha256,
        market_capability_registry_sha256=approved_plan.market_capability_registry_sha256,
        jurisdiction=approved_plan.jurisdiction,
        acquisitions=approved_plan.acquisitions,
        required_roles=approved_plan.required_roles,
    )
    with pytest.raises(LiveCaptureError, match="LIVE_PAID_PROVIDER_NOT_APPROVED"):
        LiveCaptureExecutor(tmp_path / "live").capture(
            request=request,
            plan=plan,
            acquisition_id="source.massive",
            attempt_id="attempt.massive.1",
            adapter=lambda: _response("massive"),
        )


def test_rfc10_t_013_provider_not_allowlisted_blocks(tmp_path: Path):
    request, plan = _request_plan("bse")
    request = request.model_copy(update={"policy": request.policy.model_copy(update={"allowed_provider_ids": ()})})
    with pytest.raises(LiveCaptureError, match="LIVE_PROVIDER_NOT_ALLOWED"):
        LiveCaptureExecutor(tmp_path / "live").capture(
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id="attempt.bse.1",
            adapter=lambda: _response("bse"),
        )


def test_rfc10_t_014_implicit_provider_fallback_blocks(tmp_path: Path):
    request, plan = _request_plan("bse")
    with pytest.raises(LiveCaptureError, match="LIVE_PROVIDER_FALLBACK_FORBIDDEN"):
        LiveCaptureExecutor(tmp_path / "live").capture(
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id="attempt.bse.1",
            adapter=lambda: replace(_response("bse"), provider_id="nasdaq"),
        )


def test_rfc10_t_015_public_availability_within_asof_passes(tmp_path: Path):
    *_, records = _capture_all(tmp_path, "bse")
    assert records[0].receipt.available_at_utc == AVAILABLE_AT


def test_rfc10_t_016_lookahead_after_cutoff_blocks(tmp_path: Path):
    request, plan = _request_plan("bse")
    with pytest.raises(ValidationError, match="as-of cutoff"):
        LiveCaptureExecutor(tmp_path / "live").capture(
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id="attempt.bse.1",
            adapter=lambda: replace(
                _response("bse"), available_at_utc="2026-08-25T00:00:00+00:00"
            ),
        )


def test_rfc10_t_017_captured_bytes_create_frozen_ba3_offline_replay(tmp_path: Path):
    *_, result = _bridge(tmp_path, "bse")
    assert all(item.transport == "offline_replay" for item in result.snapshot.retrieval_receipts)


def test_rfc10_t_018_ba3_locator_is_immutable_capture_locator(tmp_path: Path):
    *_, result = _bridge(tmp_path, "bse")
    assert all(
        item.original_locator.startswith("room16-capture://sha256/")
        for item in result.snapshot.retrieval_receipts
    )


def test_rfc10_t_019_live_url_remains_only_in_live_receipt(tmp_path: Path):
    *_, records, result = _bridge(tmp_path, "bse")
    assert records[0].receipt.original_locator.startswith("https://")
    assert all("https://" not in item.original_locator for item in result.snapshot.retrieval_receipts)


def test_rfc10_t_020_payload_identity_equal_live_capture_ba3(tmp_path: Path):
    *_, records, result = _bridge(tmp_path, "bse")
    assert records[0].receipt.payload_sha256 == records[0].artifact.content_sha256
    assert records[0].receipt.payload_sha256 == result.snapshot.retrieval_receipts[0].payload_sha256


def test_rfc10_t_021_source_provider_acquisition_identity_equal(tmp_path: Path):
    *_, records, result = _bridge(tmp_path, "bse")
    live = records[0].receipt
    ba3 = result.snapshot.retrieval_receipts[0]
    assert (live.acquisition_id, live.provider_id, live.source_id, live.source_type) == (
        ba3.acquisition_id,
        ba3.provider_id,
        ba3.source_id,
        ba3.source_type,
    )


def test_rfc10_t_022_payload_mismatch_live_vs_ba3_blocks(tmp_path: Path):
    *_, executor, records, result = _bridge(tmp_path, "bse")
    ba3 = result.snapshot.retrieval_receipts[0].model_copy(update={"payload_sha256": "0" * 64})
    tampered_snapshot = result.snapshot.model_copy(update={"retrieval_receipts": (ba3,)})
    tampered = LiveBridgeResult(
        tampered_snapshot, result.bindings, result.capture_set, result.closure
    )
    with pytest.raises(
        LiveCaptureError,
        match="LIVE_CAPTURE_BINDING_MISMATCH|LIVE_BA3_BINDING_MISMATCH",
    ):
        verify_live_bridge(records=records, result=tampered, capture_store_root=executor.capture_store.root)


def test_rfc10_t_023_provider_source_mismatch_live_vs_ba3_blocks(tmp_path: Path):
    *_, executor, records, result = _bridge(tmp_path, "bse")
    ba3 = result.snapshot.retrieval_receipts[0].model_copy(update={"provider_id": "nasdaq"})
    tampered_snapshot = result.snapshot.model_copy(update={"retrieval_receipts": (ba3,)})
    tampered = LiveBridgeResult(
        tampered_snapshot, result.bindings, result.capture_set, result.closure
    )
    with pytest.raises(LiveCaptureError, match="LIVE_CAPTURE_BINDING_MISMATCH|LIVE_BA3_BINDING_MISMATCH"):
        verify_live_bridge(records=records, result=tampered, capture_store_root=executor.capture_store.root)


def test_rfc10_t_024_binding_to_different_snapshot_blocks(tmp_path: Path):
    *_, executor, records, result = _bridge(tmp_path, "bse")
    binding = result.bindings[0].model_copy(update={"ba3_source_snapshot_sha256": "0" * 64})
    tampered = LiveBridgeResult(
        result.snapshot, (binding,), result.capture_set, result.closure
    )
    with pytest.raises(LiveCaptureError, match="LIVE_CAPTURE_BINDING_MISMATCH"):
        verify_live_bridge(records=records, result=tampered, capture_store_root=executor.capture_store.root)


def test_rfc10_t_025_paid_live_cost_true_ba3_replay_cost_false(tmp_path: Path):
    *_, records, result = _bridge(tmp_path, "massive")
    assert _record_for(records, "massive").receipt.variable_cost_incurred
    assert all(not item.variable_cost_incurred for item in result.snapshot.retrieval_receipts)


def test_rfc10_t_026_unchanged_source_snapshot_ir_built_from_capture(tmp_path: Path):
    *_, result = _bridge(tmp_path, "bse")
    assert result.snapshot.contract_id == "room16.compiler.source_snapshot_ir"
    assert result.snapshot.contract_version == 1
    assert hashlib.sha256(BA3_CONTRACT.read_bytes()).hexdigest() == BA3_CONTRACT_SHA256


def test_rfc10_t_027_live_binding_closes_final_snapshot_hash(tmp_path: Path):
    *_, result = _bridge(tmp_path, "bse")
    assert {item.ba3_source_snapshot_sha256 for item in result.bindings} == {
        result.snapshot.snapshot_sha256
    }


def test_rfc10_t_028_all_required_captured_bound_closes_set(tmp_path: Path):
    *_, result = _bridge(tmp_path, "nasdaq")
    assert result.capture_set.fully_closed and result.capture_set.eligible_for_native_compile
    assert all(item.terminal_state == "captured_bound" for item in result.capture_set.dispositions)


def test_rfc10_t_029_required_acquisition_missing_blocks(tmp_path: Path):
    *_, result = _bridge(tmp_path, "bse")
    with pytest.raises(ValidationError, match="exactly cover"):
        LiveCaptureSet.create(
            request_sha256=result.capture_set.request_sha256,
            acquisition_plan_sha256=result.capture_set.acquisition_plan_sha256,
            expected_acquisition_ids=("source.bse", "source.unexpected"),
            dispositions=result.capture_set.dispositions,
        )


def test_rfc10_t_030_unexpected_acquisition_source_blocks(tmp_path: Path):
    *_, result = _bridge(tmp_path, "bse")
    unexpected = LiveCaptureDisposition(
        acquisition_id="source.unexpected",
        required=False,
        terminal_state="failed_optional_dispositioned",
        failure_code="OPTIONAL_UNAVAILABLE",
    )
    with pytest.raises(ValidationError, match="exactly cover"):
        LiveCaptureSet.create(
            request_sha256=result.capture_set.request_sha256,
            acquisition_plan_sha256=result.capture_set.acquisition_plan_sha256,
            expected_acquisition_ids=("source.bse",),
            dispositions=result.capture_set.dispositions + (unexpected,),
        )


def test_rfc10_t_031_identical_concurrent_capture_converges(tmp_path: Path):
    request, plan = _request_plan("bse")
    executor = LiveCaptureExecutor(tmp_path / "live")

    def run():
        return executor.capture(
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id="attempt.bse.concurrent",
            adapter=lambda: _response("bse"),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = tuple(pool.map(lambda _: run(), range(2)))
    assert first.receipt.receipt_sha256 == second.receipt.receipt_sha256
    assert first.artifact.artifact_sha256 == second.artifact.artifact_sha256


def test_rfc10_t_032_conflicting_bytes_same_attempt_blocks(tmp_path: Path):
    request, plan = _request_plan("bse")
    executor = LiveCaptureExecutor(tmp_path / "live")
    executor.capture(
        request=request,
        plan=plan,
        acquisition_id="source.bse",
        attempt_id="attempt.bse.conflict",
        adapter=lambda: _response("bse", payload=b"one"),
    )
    with pytest.raises(LiveCaptureError, match="LIVE_DUPLICATE_ATTEMPT_CONFLICT"):
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id="attempt.bse.conflict",
            adapter=lambda: _response("bse", payload=b"two"),
        )


def test_rfc10_t_033_crash_after_capture_before_receipt_recovers(tmp_path: Path):
    request, plan = _request_plan("bse")
    executor = LiveCaptureExecutor(tmp_path / "live")
    response = _response("bse")
    executor.prepare_capture(
        request=request,
        plan=plan,
        acquisition_id="source.bse",
        attempt_id="attempt.bse.recover",
        response=response,
    )
    artifact = executor.capture_store.persist(
        response.payload,
        media_type=response.media_type,
        write_completed_at_utc=response.fetched_at_utc,
    )
    recovered = recover_after_capture(
        executor=LiveCaptureExecutor(tmp_path / "live"),
        request=request,
        plan=plan,
        acquisition_id="source.bse",
        attempt_id="attempt.bse.recover",
    )
    assert recovered.receipt.capture_artifact_sha256 == artifact.artifact_sha256


def test_rfc10_t_034_crash_after_receipt_before_binding_recovers(tmp_path: Path):
    request, plan, executor, _ = _capture_all(tmp_path, "bse")
    result = recover_bridge(
        request=request,
        plan=plan,
        executor=LiveCaptureExecutor(executor.root),
        snapshot_root=tmp_path / "snapshot",
        staged_at_utc=STAGED_AT,
    )
    assert result.bindings


def test_rfc10_t_035_crash_after_binding_before_snapshot_completion_recovers(tmp_path: Path):
    request, plan, executor, _, first = _bridge(tmp_path, "bse")
    (tmp_path / "snapshot/source_snapshot_ir.json").unlink()
    second = recover_bridge(
        request=request,
        plan=plan,
        executor=LiveCaptureExecutor(executor.root),
        snapshot_root=tmp_path / "snapshot",
        staged_at_utc=STAGED_AT,
    )
    assert first == second
    assert (tmp_path / "snapshot/source_snapshot_ir.json").is_file()


def test_rfc10_t_036_replay_twice_has_identical_ba3_hashes(tmp_path: Path):
    request, plan, executor, _ = _capture_all(tmp_path, "bse")
    hashes = []
    for name in ("snapshot-a", "snapshot-b"):
        result = recover_bridge(
            request=request,
            plan=plan,
            executor=LiveCaptureExecutor(executor.root),
            snapshot_root=tmp_path / name,
            staged_at_utc=STAGED_AT,
        )
        hashes.append((
            result.snapshot.snapshot_sha256,
            tuple(item.ba3_retrieval_receipt_sha256 for item in result.bindings),
        ))
    assert hashes[0] == hashes[1]


@pytest.mark.parametrize(
    ("provider", "test_id"),
    (("sec", "RFC10-T-037"), ("nasdaq", "RFC10-T-038"), ("bse", "RFC10-T-039"), ("massive", "RFC10-T-040")),
)
def test_rfc10_t_037_to_040_provider_adapter_deterministic_harness(
    tmp_path: Path, provider: str, test_id: str
):
    selected = "massive" if provider == "massive" else "bse" if provider == "bse" else "nasdaq"
    *_, records = _capture_all(tmp_path, selected)
    record = _record_for(records, provider)
    request, plan = _request_plan(selected)
    item = next(item for item in plan.acquisitions if item.provider_id == provider)
    assert len(adapter_implementation_sha256(item)) == 64
    assert record.receipt.adapter_implementation_sha256 == adapter_implementation_sha256(item)
    assert test_id.startswith("RFC10-T-0")


def test_rfc10_t_044_live_layer_has_no_semantic_authority():
    assert verify_authority_boundary()["status"] == "PASS"


def test_rfc10_bridge_contract_rejects_frozen_ba3_live_transport():
    fields = RetrievalReceiptIR.model_fields["transport"].annotation
    assert "live_acquisition" not in str(fields)
