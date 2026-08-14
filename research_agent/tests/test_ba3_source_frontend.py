from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.compiler_foundation.canonical import canonical_bytes
from research_agent.compiler_foundation.contracts import CompilerLayer
from research_agent.semantic_compiler.source_frontend.adapter_contract import (
    ADAPTER_CONTRACT_PATH,
    SourceAdapterContractError,
    adapter_descriptor,
    load_adapter_contract,
    verify_adapter_implementation,
)
from research_agent.semantic_compiler.source_frontend.contracts import SourceAcquisitionIR
from research_agent.semantic_compiler.source_frontend.envelopes import (
    compile_request_envelope,
    source_acquisition_envelope,
    source_snapshot_envelope,
)
from research_agent.semantic_compiler.source_frontend.offline import (
    OfflineSourceInput,
    freeze_offline_sources,
    verify_source_snapshot,
)
from research_agent.semantic_compiler.source_frontend.planner import (
    SourceFrontendError,
    build_compile_request,
    plan_source_acquisition,
)
from research_agent.semantic_compiler.source_frontend.registry_binding import (
    BINDING_PATH,
    SourceAdapterBindingError,
    load_source_adapter_binding,
    source_types_for_provider,
)


def _resolution(*, jurisdiction: str = "US") -> dict[str, object]:
    if jurisdiction == "HU":
        return {
            "input": "A0Q483",
            "inputKind": "wkn",
            "ticker": "ANY",
            "companyName": "ANY Security Printing Company PLC",
            "exchange": "Budapest Stock Exchange",
            "exchangeCode": "BSE",
            "jurisdiction": "HU",
            "isin": "HU0000093257",
            "wkn": "A0Q483",
            "source": "local_adapter_identity",
            "status": "supported",
            "runtimeReady": True,
        }
    return {
        "input": "WM",
        "inputKind": "ticker",
        "ticker": "WM",
        "companyName": "Waste Management, Inc.",
        "exchange": "New York Stock Exchange",
        "exchangeCode": "NYQ",
        "jurisdiction": "US",
        "source": "resolver_fixture",
        "status": "supported",
        "runtimeReady": True,
    }


def _us_request():
    return build_compile_request(
        _resolution(),
        as_of_date="2026-08-11",
        allowed_provider_ids=("nasdaq", "sec"),
        available_configuration_ids=("ROOM16_SEC_USER_AGENT",),
    )


def _inputs(tmp_path: Path) -> tuple[OfflineSourceInput, ...]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    sec = tmp_path / "filing.json"
    price = tmp_path / "prices.csv"
    sec.write_text('{"ticker":"WM","revenue":123}', encoding="utf-8")
    price.write_text("date,close\n2026-08-11,100\n", encoding="utf-8")
    return (
        OfflineSourceInput(
            acquisition_id="source.sec",
            source_id="sec:wm:10q",
            source_type="sec_filing",
            provider_id="sec",
            path=sec,
            original_locator="https://www.sec.gov/Archives/wm-10q.json",
            retrieved_at="2026-08-11T18:00:00+00:00",
            available_at="2026-08-11T12:00:00+00:00",
            published_at="2026-08-11T12:00:00+00:00",
            filing_date="2026-08-11",
            transport="offline_fixture",
        ),
        OfflineSourceInput(
            acquisition_id="source.nasdaq",
            source_id="nasdaq:wm:ohlcv",
            source_type="exchange_ohlcv",
            provider_id="nasdaq",
            path=price,
            original_locator="https://www.nasdaq.com/WM.csv",
            retrieved_at="2026-08-11T23:00:00+00:00",
            available_at="2026-08-11T22:00:00+00:00",
            published_at="2026-08-11T22:00:00+00:00",
            transport="offline_fixture",
        ),
    )


def test_compile_request_and_plan_are_deterministic() -> None:
    request_a = _us_request()
    request_b = _us_request()
    plan_a = plan_source_acquisition(request_a)
    plan_b = plan_source_acquisition(request_b)
    assert request_a.request_sha256 == request_b.request_sha256
    assert plan_a.plan_sha256 == plan_b.plan_sha256
    assert [item.provider_id for item in plan_a.acquisitions] == ["nasdaq", "sec"]
    assert plan_a.required_roles == ("fundamentals", "issuer_identity", "market_prices")


def test_bse_uses_one_authority_adapter_without_fallback() -> None:
    request = build_compile_request(
        _resolution(jurisdiction="HU"),
        as_of_date="2026-08-13",
        allowed_provider_ids=("bse",),
    )
    plan = plan_source_acquisition(request)
    assert [item.provider_id for item in plan.acquisitions] == ["bse"]
    assert plan.provider_fallback_allowed is False


def test_unsupported_market_fails_before_compile_request() -> None:
    resolution = {
        **_resolution(),
        "ticker": "7203.T",
        "companyName": "Toyota Motor Corporation",
        "jurisdiction": "JP",
        "status": "recognized_unsupported",
        "runtimeReady": False,
        "requiredAdapter": "edinet",
    }
    with pytest.raises(SourceFrontendError, match="UNKNOWN_REGISTRY_ID") as caught:
        build_compile_request(
            resolution,
            as_of_date="2026-08-11",
            allowed_provider_ids=(),
        )
    assert caught.value.diagnostic.details["diagnostic_registry_id"] == "unknown_registry_id"


def test_missing_company_name_fails_closed() -> None:
    resolution = {**_resolution(), "companyName": None}
    with pytest.raises(SourceFrontendError, match="VERSION_UNSUPPORTED"):
        build_compile_request(
            resolution,
            as_of_date="2026-08-11",
            allowed_provider_ids=("nasdaq", "sec"),
        )


def test_provider_must_be_explicitly_allowed() -> None:
    request = build_compile_request(
        _resolution(),
        as_of_date="2026-08-11",
        allowed_provider_ids=("sec",),
        available_configuration_ids=("ROOM16_SEC_USER_AGENT",),
    )
    with pytest.raises(SourceFrontendError, match="UNKNOWN_REGISTRY_ID"):
        plan_source_acquisition(request)


def test_possible_cost_provider_requires_explicit_approval() -> None:
    request = build_compile_request(
        _resolution(),
        as_of_date="2026-08-11",
        allowed_provider_ids=("massive", "sec"),
        available_configuration_ids=("ROOM16_SEC_USER_AGENT",),
    )
    with pytest.raises(SourceFrontendError, match="VERSION_UNSUPPORTED"):
        plan_source_acquisition(request, price_provider_id="massive")
    approved = build_compile_request(
        _resolution(),
        as_of_date="2026-08-11",
        allowed_provider_ids=("massive", "sec"),
        approved_paid_provider_ids=("massive",),
        available_configuration_ids=("ROOM16_SEC_USER_AGENT",),
    )
    assert [
        item.provider_id
        for item in plan_source_acquisition(
            approved, price_provider_id="massive"
        ).acquisitions
    ] == ["massive", "sec"]


def test_offline_snapshot_is_content_addressed_and_replay_stable(tmp_path: Path) -> None:
    request = _us_request()
    plan = plan_source_acquisition(request)
    inputs = _inputs(tmp_path / "input")
    first = freeze_offline_sources(
        request=request,
        plan=plan,
        inputs=inputs,
        snapshot_root=tmp_path / "first",
    )
    second = freeze_offline_sources(
        request=request,
        plan=plan,
        inputs=inputs,
        snapshot_root=tmp_path / "second",
    )
    assert first.snapshot_sha256 == second.snapshot_sha256
    assert len(first.artifacts) == 2
    assert len(first.retrieval_receipts) == 2
    assert all(item.path.startswith("sources/") for item in first.artifacts)
    verify_source_snapshot(first, snapshot_root=tmp_path / "first")


def test_snapshot_tamper_is_blocked(tmp_path: Path) -> None:
    request = _us_request()
    plan = plan_source_acquisition(request)
    snapshot = freeze_offline_sources(
        request=request,
        plan=plan,
        inputs=_inputs(tmp_path / "input"),
        snapshot_root=tmp_path / "snapshot",
    )
    target = tmp_path / "snapshot" / snapshot.artifacts[0].path
    target.write_bytes(target.read_bytes() + b"tamper")
    with pytest.raises(SourceFrontendError, match="CONTRACT_HASH_MISMATCH"):
        verify_source_snapshot(snapshot, snapshot_root=tmp_path / "snapshot")


def test_lookahead_source_is_blocked(tmp_path: Path) -> None:
    request = _us_request()
    plan = plan_source_acquisition(request)
    values = list(_inputs(tmp_path / "input"))
    values[0] = OfflineSourceInput(
        **{
            **values[0].__dict__,
            "available_at": "2026-08-12T00:00:00+00:00",
        }
    )
    with pytest.raises(SourceFrontendError, match="VERSION_UNSUPPORTED") as caught:
        freeze_offline_sources(
            request=request,
            plan=plan,
            inputs=tuple(values),
            snapshot_root=tmp_path / "snapshot",
        )
    assert caught.value.diagnostic.root_cause_ref == "source_lookahead_detected"


def test_incomplete_acquisition_payload_set_is_blocked(tmp_path: Path) -> None:
    request = _us_request()
    plan = plan_source_acquisition(request)
    with pytest.raises(SourceFrontendError, match="UNKNOWN_REGISTRY_ID"):
        freeze_offline_sources(
            request=request,
            plan=plan,
            inputs=(_inputs(tmp_path / "input")[0],),
            snapshot_root=tmp_path / "snapshot",
        )


def test_ir_envelopes_bind_exact_layers_and_hashes(tmp_path: Path) -> None:
    request = _us_request()
    plan = plan_source_acquisition(request)
    snapshot = freeze_offline_sources(
        request=request,
        plan=plan,
        inputs=_inputs(tmp_path / "input"),
        snapshot_root=tmp_path / "snapshot",
    )
    envelopes = (
        compile_request_envelope(request),
        source_acquisition_envelope(plan),
        source_snapshot_envelope(snapshot),
    )
    assert [item.layer for item in envelopes] == [
        CompilerLayer.L0_COMPILE_INTAKE,
        CompilerLayer.L1_SOURCE_ACQUISITION,
        CompilerLayer.L2_SOURCE_SNAPSHOT,
    ]
    for envelope in envelopes:
        envelope.verify_hash()


def test_contract_version_and_hash_tamper_fail_closed() -> None:
    plan = plan_source_acquisition(_us_request())
    payload = plan.model_dump(mode="json")
    payload["contract_version"] = 2
    with pytest.raises(ValidationError):
        SourceAcquisitionIR.model_validate(payload)
    payload = plan.model_dump(mode="json")
    payload["plan_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="plan hash mismatch"):
        SourceAcquisitionIR.model_validate(payload)


def test_pass_contracts_have_fixed_order_no_skip_and_all_behavior_contracts() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "semantic_compiler/source_frontend/config/source_frontend_pass_contracts.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["contract_version"] == 1
    passes = payload["passes"]
    assert [item["ordinal"] for item in passes] == [0, 1, 2, 3]
    assert len({item["pass_id"] for item in passes}) == 4
    for item in passes:
        assert item["skippable"] is False
        assert item["side_effect_contract"]
        assert item["determinism_contract"]
        assert item["cache_contract"]
        assert item["replay_contract"]
        assert item["failure_contract"] == "fail_closed_diagnostic"
        assert isinstance(item["registry_dependencies"], list)


def test_source_adapter_registry_binding_positive_negative_tamper_version_unknown(
    tmp_path: Path,
) -> None:
    payload = load_source_adapter_binding()
    assert payload["source_registry"]["owner"] == "research"
    assert source_types_for_provider("sec") == ("company_ir", "sec_filing")
    with pytest.raises(SourceAdapterBindingError, match="provider_binding_unknown"):
        source_types_for_provider("unknown")

    tampered = json.loads(BINDING_PATH.read_text(encoding="utf-8"))
    tampered["source_registry"]["sha256"] = "0" * 64
    tamper_path = tmp_path / "tampered.json"
    tamper_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(SourceAdapterBindingError, match="hash_mismatch"):
        load_source_adapter_binding(tamper_path)

    versioned = json.loads(BINDING_PATH.read_text(encoding="utf-8"))
    versioned["contract_version"] = 2
    version_path = tmp_path / "version.json"
    version_path.write_text(json.dumps(versioned), encoding="utf-8")
    with pytest.raises(SourceAdapterBindingError, match="version_unsupported"):
        load_source_adapter_binding(version_path)


def test_existing_adapter_contracts_positive_negative_tamper_version_unknown(
    tmp_path: Path,
) -> None:
    payload = load_adapter_contract()
    assert [item["provider_id"] for item in payload["adapters"]] == [
        "bse",
        "massive",
        "nasdaq",
        "sec",
    ]
    for provider_id in ("bse", "massive", "nasdaq", "sec"):
        assert verify_adapter_implementation(provider_id)["provider_id"] == provider_id
    with pytest.raises(SourceAdapterContractError, match="adapter_contract_unknown"):
        adapter_descriptor("unknown")

    versioned = json.loads(ADAPTER_CONTRACT_PATH.read_text(encoding="utf-8"))
    versioned["contract_version"] = 2
    version_path = tmp_path / "adapter-version.json"
    version_path.write_text(json.dumps(versioned), encoding="utf-8")
    with pytest.raises(SourceAdapterContractError, match="version_unsupported"):
        load_adapter_contract(version_path)

    tampered = json.loads(ADAPTER_CONTRACT_PATH.read_text(encoding="utf-8"))
    tampered["adapters"][0]["required_methods"].append("method_that_does_not_exist")
    tampered["adapters"][0]["required_methods"].sort()
    tamper_path = tmp_path / "adapter-tamper.json"
    tamper_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(SourceAdapterContractError, match="adapter_methods_missing"):
        verify_adapter_implementation("bse", path=tamper_path)


def test_ba3_canonical_hash_matches_node_cross_language() -> None:
    payload = _us_request().model_dump(mode="json")
    expected = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    script = """
const crypto = require('node:crypto');
let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => raw += chunk);
process.stdin.on('end', () => {
  const normalize = value => Array.isArray(value)
    ? value.map(normalize)
    : value && typeof value === 'object'
      ? Object.fromEntries(Object.keys(value).sort().map(key => [key, normalize(value[key])]))
      : value;
  const canonical = JSON.stringify(normalize(JSON.parse(raw)));
  process.stdout.write(crypto.createHash('sha256').update(canonical).digest('hex'));
});
"""
    result = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(payload),
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == expected
