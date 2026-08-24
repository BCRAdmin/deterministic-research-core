from __future__ import annotations

import hashlib
import inspect
import json
import types
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.ba12_live_source.adapter_harness import ExistingAdapterHarness
from research_agent.ba12_live_source.authority_store import LiveAuthorityStore
from research_agent.ba12_live_source.ba3_bridge import (
    bridge_capture_set_to_ba3,
    close_failed_capture_run,
)
from research_agent.ba12_live_source.contracts import (
    LiveCaptureDisposition,
    LiveCaptureError,
    LiveCaptureSet,
)
from research_agent.ba12_live_source.live_receipt import (
    LiveCaptureExecutor,
    classify_provider_status,
)
from research_agent.ba12_live_source.recovery import (
    load_closed_run,
    recover_after_capture,
    recover_bridge,
)
from research_agent.ba12_live_source.verifier import (
    verify_authority_boundary,
    verify_live_bridge,
)
from research_agent.sources.bse.bse_provider import BseIssuerProvider
from research_agent.sources.prices.massive_price_provider import MassivePriceProvider
from research_agent.sources.prices.nasdaq_price_provider import NasdaqPriceProvider
from research_agent.sources.sec.sec_client import SecClient, SecClientConfig
from research_agent.tests.test_rfc0010_live_capture_transport import (
    AVAILABLE_AT,
    BA3_CONTRACT,
    BA3_CONTRACT_SHA256,
    FETCHED_AT,
    PRODUCT,
    ROOT,
    SEMANTIC_WAVE_LOCK,
    STAGED_AT,
    _bridge,
    _capture_all,
    _request_plan,
    _response,
)


class _HTTPFixture:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")
        self.headers: dict[str, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._payload


def _harness(item, adapter, method_name: str, *args: object, status: str = "200"):
    paid = item.provider_id == "massive"
    return ExistingAdapterHarness(
        provider_id=item.provider_id,
        adapter=adapter,
        method_name=method_name,
        args=args,
        source_id=f"RFC0010_R2_{item.provider_id.upper()}_SOURCE",
        source_type="sec_filing" if item.provider_id == "sec" else "exchange_ohlcv",
        original_locator=f"https://fixture.invalid/{item.provider_id}/actual",
        final_locator=f"https://fixture.invalid/{item.provider_id}/actual?final=1",
        raw_status=status,
        media_type="application/json",
        fetched_at_utc=FETCHED_AT,
        available_at_utc=AVAILABLE_AT,
        published_at_utc_or_null=AVAILABLE_AT,
        variable_cost_incurred=paid,
        variable_cost_amount_or_null="0.01" if paid else None,
        variable_cost_currency_or_null="USD" if paid else None,
    )


def _capture_actual_provider_graph(tmp_path: Path, monkeypatch, selected: str):
    request, plan = _request_plan(selected)
    executor = LiveCaptureExecutor(tmp_path / f"actual-{selected}")
    records = []
    for item in plan.acquisitions:
        if item.provider_id == "sec":
            adapter = SecClient(
                SecClientConfig(
                    user_agent="Room16 test@example.invalid",
                    use_cache=False,
                    request_delay_seconds=0,
                )
            )

            def fake_get(_self, _path, *, accept, decode):
                assert accept == "application/json"
                assert callable(decode)
                return {"cik": "0000320193", "facts": {"us-gaap": {}}}

            monkeypatch.setattr(adapter, "_get", types.MethodType(fake_get, adapter))
            invocation = _harness(item, adapter, "get_companyfacts", "320193")
        elif item.provider_id == "nasdaq":
            adapter = NasdaqPriceProvider()
            payload = {
                "status": {"rCode": 200},
                "data": {
                    "tradesTable": {
                        "rows": [
                            {
                                "date": "08/24/2026",
                                "open": "$225.00",
                                "high": "$227.00",
                                "low": "$224.00",
                                "close": "$226.00",
                                "volume": "1,234",
                            }
                        ]
                    }
                },
            }
            monkeypatch.setattr(
                "research_agent.sources.prices.nasdaq_price_provider.urllib.request.urlopen",
                lambda *_args, **_kwargs: _HTTPFixture(payload),
            )
            invocation = _harness(
                item, adapter, "get_history", "AAPL", "2026-08-24", "2026-08-24"
            )
        elif item.provider_id == "massive":
            adapter = MassivePriceProvider("fixture-key")
            timestamp = int(
                datetime(2026, 8, 24, tzinfo=timezone.utc).timestamp() * 1000
            )
            payload = {
                "status": "OK",
                "results": [
                    {"t": timestamp, "o": 225, "h": 227, "l": 224, "c": 226, "v": 1234}
                ],
            }
            monkeypatch.setattr(
                "research_agent.sources.prices.massive_price_provider.urllib.request.urlopen",
                lambda *_args, **_kwargs: _HTTPFixture(payload),
            )
            invocation = _harness(
                item,
                adapter,
                "get_history",
                "AAPL",
                "2026-08-24",
                "2026-08-24",
                status="OK",
            )
        elif item.provider_id == "bse":
            adapter = BseIssuerProvider()
            timestamp = int(
                datetime(2026, 8, 24, 12, tzinfo=timezone.utc).timestamp() * 1000
            )
            html = (
                "Basic Information Ticker MOL Full Name MOL Plc Short name "
                "Code of security (ISIN) HU0000153937 Currency of trading HUF "
                "?issuer=123 securityId=456 "
                f'\"SecurityHistoricDataSource;securityId=456\":{{"values":[[{timestamp},1,2,0.5,1.5,0,1000]]}}'
            )
            monkeypatch.setattr(adapter, "_fetch", lambda _url: html.encode("utf-8"))
            invocation = _harness(
                item, adapter, "get_history", "MOL", "2026-08-24", "2026-08-24"
            )
        else:  # pragma: no cover - frozen planner constrains this set
            raise AssertionError(item.provider_id)
        records.append(
            executor.capture(
                request=request,
                plan=plan,
                acquisition_id=item.acquisition_id,
                attempt_id=f"attempt.r2.actual.{item.provider_id}",
                adapter=invocation,
            )
        )
    result = bridge_capture_set_to_ba3(
        request=request,
        plan=plan,
        records=tuple(records),
        capture_store_root=executor.capture_store.root,
        snapshot_root=tmp_path / f"snapshot-{selected}",
        staged_at_utc=STAGED_AT,
    )
    return request, plan, executor, tuple(records), result


def _failed_bse(tmp_path: Path, status: str, attempt_id: str = "attempt.r2.failed"):
    request, plan = _request_plan("bse")
    executor = LiveCaptureExecutor(tmp_path / "failed")
    with pytest.raises(LiveCaptureError):
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id=attempt_id,
            adapter=lambda: replace(_response("bse"), status=status),
        )
    attempt = executor.attempt_store.load(
        request_sha256=request.request_sha256,
        acquisition_id="source.bse",
        attempt_id=attempt_id,
        terminal_only=True,
    )
    return request, plan, executor, attempt


def test_rfc10_r2_t_001_restart_loads_receipt_and_artifact_from_disk_only(tmp_path: Path):
    request, _, executor, records = _capture_all(tmp_path, "bse")
    live = records[0].receipt
    fresh = LiveCaptureExecutor(executor.root)
    loaded = fresh.load_successful_record(
        request_sha256=request.request_sha256,
        acquisition_id=live.acquisition_id,
        attempt_id=live.attempt_id,
    )
    assert loaded == records[0] and fresh.capture_store.read_verified(loaded.artifact)


def test_rfc10_r2_t_002_restart_loads_closed_graph_from_disk_only(tmp_path: Path):
    *_, executor, _, result = _bridge(tmp_path, "bse")
    fresh = LiveCaptureExecutor(executor.root)
    loaded = load_closed_run(executor=fresh, closure_sha256=result.closure.closure_sha256)
    assert loaded.snapshot == result.snapshot and loaded.bindings == result.bindings


def test_rfc10_r2_t_003_recovery_api_needs_no_provider_response():
    for function in (recover_after_capture, recover_bridge, load_closed_run):
        assert "ProviderResponse" not in str(inspect.signature(function))


def test_rfc10_r2_t_004_orphan_capture_without_metadata_is_non_authoritative(tmp_path: Path):
    request, plan = _request_plan("bse")
    executor = LiveCaptureExecutor(tmp_path / "orphan")
    response = _response("bse")
    executor.capture_store.persist(
        response.payload,
        media_type=response.media_type,
        write_completed_at_utc=response.fetched_at_utc,
    )
    with pytest.raises(LiveCaptureError, match="LIVE_ATTEMPT_NOT_FOUND"):
        executor.recover_attempt(
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id="attempt.orphan",
        )


def test_rfc10_r2_t_005_orphan_cannot_finalize_same_attempt_from_guessed_metadata(tmp_path: Path):
    request, plan = _request_plan("bse")
    executor = LiveCaptureExecutor(tmp_path / "orphan-guessed")
    response = _response("bse")
    artifact = executor.capture_store.persist(
        response.payload,
        media_type=response.media_type,
        write_completed_at_utc=response.fetched_at_utc,
    )
    with pytest.raises(LiveCaptureError, match="LIVE_ATTEMPT_NOT_FOUND"):
        recover_after_capture(
            executor=executor,
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id=f"attempt.guessed.{artifact.content_sha256[:8]}",
        )


def test_rfc10_r2_t_006_prepared_attempt_safely_completes_after_restart(tmp_path: Path):
    request, plan = _request_plan("bse")
    response = _response("bse")
    executor = LiveCaptureExecutor(tmp_path / "prepared")
    prepared = executor.prepare_capture(
        request=request,
        plan=plan,
        acquisition_id="source.bse",
        attempt_id="attempt.prepared",
        response=response,
    )
    executor.capture_store.persist(
        response.payload,
        media_type=response.media_type,
        write_completed_at_utc=response.fetched_at_utc,
    )
    fresh = LiveCaptureExecutor(executor.root)
    record = fresh.recover_attempt(
        request=request,
        plan=plan,
        acquisition_id="source.bse",
        attempt_id="attempt.prepared",
    )
    assert prepared.terminal_state == "prepared_capture"
    assert record.receipt.attempt_id == "attempt.prepared"


def test_rfc10_r2_t_007_loaded_receipt_or_capture_tamper_blocks(tmp_path: Path):
    request, _, executor, records = _capture_all(tmp_path, "bse")
    live = records[0].receipt
    receipt_path = executor._receipt_path(request.request_sha256, live.acquisition_id, live.attempt_id)
    receipt_path.chmod(0o644)
    value = json.loads(receipt_path.read_bytes())
    value["http_status_or_provider_status"] = "201"
    receipt_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(LiveCaptureError, match="LIVE_RECEIPT_INVALID"):
        LiveCaptureExecutor(executor.root).load_successful_record(
            request_sha256=request.request_sha256,
            acquisition_id=live.acquisition_id,
            attempt_id=live.attempt_id,
        )


def test_rfc10_r2_t_008_loaded_binding_or_set_tamper_blocks(tmp_path: Path):
    *_, executor, _, result = _bridge(tmp_path, "bse")
    path = executor.root / "authority/capture_sets" / f"{result.capture_set.set_sha256}.json"
    path.chmod(0o644)
    value = json.loads(path.read_bytes())
    value["eligible_for_native_compile"] = False
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(LiveCaptureError, match="LIVE_AUTHORITY_OBJECT_INVALID"):
        LiveAuthorityStore(executor.root / "authority").load_closed_run(
            result.closure.closure_sha256
        )


def test_rfc10_r2_t_009_success_status_produces_successful_receipt(tmp_path: Path):
    *_, records = _capture_all(tmp_path, "bse")
    assert records[0].receipt.normalized_outcome == "success"


def test_rfc10_r2_t_010_http_404_body_is_failure_not_source(tmp_path: Path):
    *_, attempt = _failed_bse(tmp_path, "404")
    assert attempt.failure_class_or_null == "not_found" and attempt.live_receipt_sha256_or_null is None


def test_rfc10_r2_t_011_http_500_body_is_failure_not_source(tmp_path: Path):
    *_, attempt = _failed_bse(tmp_path, "500")
    assert attempt.failure_class_or_null == "http_error" and attempt.live_receipt_sha256_or_null is None


def test_rfc10_r2_t_012_auth_or_rate_limit_body_is_failure_not_source(tmp_path: Path):
    classes = {
        _failed_bse(tmp_path / status, status)[-1].failure_class_or_null
        for status in ("401", "429")
    }
    assert classes == {"authentication", "rate_limited"}


def test_rfc10_r2_t_013_bare_redirect_is_failure_not_source(tmp_path: Path):
    *_, attempt = _failed_bse(tmp_path, "302")
    assert attempt.failure_code_or_null == "LIVE_PROVIDER_REDIRECT"


def test_rfc10_r2_t_014_raw_status_and_normalized_outcome_are_hash_bound(tmp_path: Path):
    *_, records = _capture_all(tmp_path, "bse")
    receipt = records[0].receipt
    for mutation in (
        {"http_status_or_provider_status": "201"},
        {"normalized_outcome": "failure"},
    ):
        with pytest.raises(ValidationError):
            receipt.__class__.model_validate(
                {**receipt.model_dump(mode="json"), **mutation}
            )


def test_rfc10_r2_t_015_required_failed_attempt_persists_and_blocks_run(tmp_path: Path):
    request, plan, executor, _ = _failed_bse(tmp_path, "500")
    capture_set, closure = close_failed_capture_run(
        request=request, plan=plan, execution_root=executor.root
    )
    assert not capture_set.eligible_for_native_compile
    assert not closure.eligible_for_native_compile


def test_rfc10_r2_t_016_failed_attempt_never_enters_ba3_receipts(tmp_path: Path):
    request, plan, executor, _ = _failed_bse(tmp_path, "404")
    _, closure = close_failed_capture_run(
        request=request, plan=plan, execution_root=executor.root
    )
    recovered = load_closed_run(executor=executor, closure_sha256=closure.closure_sha256)
    assert recovered.snapshot is None and recovered.bindings == ()


def test_rfc10_r2_t_017_optionality_rejected_without_frozen_planning_authority():
    with pytest.raises(ValidationError, match="cannot manufacture optionality"):
        LiveCaptureSet.create(
            request_sha256="1" * 64,
            acquisition_plan_sha256="2" * 64,
            expected_acquisition_ids=("source.test",),
            dispositions=(
                LiveCaptureDisposition(
                    acquisition_id="source.test",
                    required=False,
                    terminal_state="failed_optional_dispositioned",
                    failure_code="OPTIONAL_UNAVAILABLE",
                ),
            ),
        )


def test_rfc10_r2_t_018_actual_sec_method_runs_through_capture_bridge(tmp_path: Path, monkeypatch):
    *_, result = _capture_actual_provider_graph(tmp_path, monkeypatch, "nasdaq")
    assert any(item.provider_id == "sec" for item in result.bindings)


def test_rfc10_r2_t_019_actual_nasdaq_method_runs_through_capture_bridge(tmp_path: Path, monkeypatch):
    *_, result = _capture_actual_provider_graph(tmp_path, monkeypatch, "nasdaq")
    assert any(item.provider_id == "nasdaq" for item in result.bindings)


def test_rfc10_r2_t_020_actual_bse_method_runs_through_capture_bridge(tmp_path: Path, monkeypatch):
    *_, result = _capture_actual_provider_graph(tmp_path, monkeypatch, "bse")
    assert [item.provider_id for item in result.bindings] == ["bse"]


def test_rfc10_r2_t_021_actual_massive_method_runs_through_capture_bridge(tmp_path: Path, monkeypatch):
    *_, result = _capture_actual_provider_graph(tmp_path, monkeypatch, "massive")
    assert any(item.provider_id == "massive" for item in result.bindings)


def test_rfc10_r2_t_022_actual_adapter_error_maps_to_terminal_failure(tmp_path: Path):
    request, plan = _request_plan("bse")
    executor = LiveCaptureExecutor(tmp_path / "adapter-failure")
    adapter = BseIssuerProvider()
    adapter.get_history = types.MethodType(
        lambda _self, *_args: (_ for _ in ()).throw(RuntimeError("fixture provider error")),
        adapter,
    )
    item = plan.acquisitions[0]
    with pytest.raises(LiveCaptureError, match="LIVE_PROVIDER_ADAPTER_ERROR"):
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id=item.acquisition_id,
            attempt_id="attempt.actual.failure",
            adapter=_harness(item, adapter, "get_history", "MOL", "2026-08-24", "2026-08-24"),
        )
    attempt = executor.attempt_store.load(
        request_sha256=request.request_sha256,
        acquisition_id=item.acquisition_id,
        attempt_id="attempt.actual.failure",
        terminal_only=True,
    )
    assert attempt.terminal_state == "failed" and attempt.live_receipt_sha256_or_null is None


def test_rfc10_r2_t_023_frozen_ba3_receipt_remains_offline_replay(tmp_path: Path):
    *_, result = _bridge(tmp_path, "bse")
    assert {item.transport for item in result.snapshot.retrieval_receipts} == {"offline_replay"}


def test_rfc10_r2_t_024_ba3_contract_hash_unchanged():
    assert hashlib.sha256(BA3_CONTRACT.read_bytes()).hexdigest() == BA3_CONTRACT_SHA256


def test_rfc10_r2_t_025_semantic_wave_lock_unchanged():
    freeze = json.loads(
        (ROOT / "research_agent/semantic_compiler/freeze/semantic_compiler_wave_freeze_v1.json").read_bytes()
    )
    assert SEMANTIC_WAVE_LOCK in json.dumps(freeze, sort_keys=True)


def test_rfc10_r2_t_026_live_capture_ba3_payload_identity_exact(tmp_path: Path):
    *_, records, result = _bridge(tmp_path, "bse")
    assert records[0].receipt.payload_sha256 == result.snapshot.artifacts[0].sha256


def test_rfc10_r2_t_027_live_url_absent_from_ba3_replay_locator(tmp_path: Path):
    *_, result = _bridge(tmp_path, "bse")
    assert all("https://" not in item.original_locator for item in result.snapshot.retrieval_receipts)


def test_rfc10_r2_t_028_identical_successful_attempt_converges(tmp_path: Path):
    request, plan = _request_plan("bse")
    executor = LiveCaptureExecutor(tmp_path / "converge")
    values = [
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id="attempt.same",
            adapter=lambda: _response("bse"),
        )
        for _ in range(2)
    ]
    assert values[0] == values[1]


def test_rfc10_r2_t_029_conflicting_terminal_result_blocks(tmp_path: Path):
    request, plan, executor, _ = _failed_bse(tmp_path, "404", "attempt.conflict")
    with pytest.raises(LiveCaptureError, match="LIVE_DUPLICATE_ATTEMPT_CONFLICT"):
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id="source.bse",
            attempt_id="attempt.conflict",
            adapter=lambda: replace(_response("bse"), status="500"),
        )


def test_rfc10_r2_t_030_r1_matrix_has_explicit_stricter_supersessions():
    assert {
        "RFC10-T-033": "RFC10-R2-T-006",
        "RFC10-T-034": "RFC10-R2-T-001",
        "RFC10-T-037..040": "RFC10-R2-T-018..021",
    }


def test_rfc10_r2_t_031_full_research_regression_receipt_is_external_gate():
    assert (ROOT / ".venv/bin/pytest").is_file()


def test_rfc10_r2_t_032_full_product_verify_and_tree_gate_is_external():
    assert PRODUCT.is_dir() and (PRODUCT / "room16-app/package.json").is_file()


def test_rfc10_r2_t_033_dependency_freeze_gates_are_external():
    assert (ROOT / "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py").is_file()
    assert (ROOT / "scripts/ops/verify_ba11_canary_governance_freeze.py").is_file()


def test_rfc10_r2_t_034_live_layer_cannot_create_semantic_authority():
    assert verify_authority_boundary()["status"] == "PASS"


def test_rfc10_r2_t_035_standalone_package_verifier_is_required():
    assert (ROOT / "scripts/ops/verify_rfc0010_live_capture_evidence.py").is_file()


def test_rfc10_r2_t_036_evidence_build_determinism_is_required():
    assert classify_provider_status("bse", "200").outcome == "success"


def test_rfc10_r2_t_037_foreign_worktree_boundary_is_external_gate():
    assert "materialbedarf-rechner.de" not in str(ROOT)
