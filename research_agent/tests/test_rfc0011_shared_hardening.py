from __future__ import annotations

import hashlib
import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from research_agent.alpha_shared.contracts import (
    DiscoveryRequestIR,
    DocumentObservationIR,
    SupplementalSourceError,
    SupplementalSourcePolicyIR,
)
from research_agent.alpha_shared.document_normalizer import (
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.metric_resolver import MetricCandidate, resolve_metric
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.operations_ledger import (
    OperationsLedger,
    OperationsLedgerError,
    verify_batch_gate,
)
from research_agent.alpha_shared.period_freshness import (
    PeriodCandidate,
    classify_period,
    derived_inputs_compatible,
)
from research_agent.alpha_shared.source_authority import (
    NetworkResponse,
    STRUCTURED_REGULATORY_SOURCE_PROFILE,
    SupplementalSourceAuthority,
)

ROOT = Path(__file__).resolve().parents[2]
FETCHED = "2026-08-27T10:00:00Z"


def _hash(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _policy(**updates: object) -> SupplementalSourcePolicyIR:
    values: dict[str, object] = {
        "base_request_sha256": "0" * 64,
        "ticker": "TEST",
        "canonical_company_name": "Neutral Fixture Corp",
        "issuer_cik": "1234",
        "as_of_date": "2026-08-27",
        "allowed_source_family_ids": (
            "sec_filed_exhibit",
            "sec_primary_document",
            "structured_regulatory_dataset",
        ),
        "allowed_domains": ("data.sec.gov", "www.sec.gov"),
        "allowed_media_types": ("application/json", "text/html", "text/plain"),
        "allowed_sec_forms": ("10-K", "10-Q", "8-K"),
        "max_discovery_requests": 3,
        "max_candidates": 20,
        "max_selected_documents": 3,
        "max_bytes_per_document": 1_000_000,
        "discovery_lookback_days": 550,
        "paid_provider_ids_allowed": (),
        "network_mode": "live_acquisition",
    }
    values.update(updates)
    return SupplementalSourcePolicyIR.create(**values)


def _request(policy: SupplementalSourcePolicyIR) -> DiscoveryRequestIR:
    return DiscoveryRequestIR.create(
        request_id="discovery.sec.submissions",
        policy_sha256=policy.policy_sha256,
        source_family_id="sec_primary_document",
        locator="https://data.sec.gov/submissions/CIK0000001234.json",
    )


def _submissions(rows: int = 2) -> bytes:
    values = {
        "cik": "1234",
        "filings": {
            "recent": {
                "accessionNumber": ["0000001234-26-000001", "0000001234-26-000002"][:rows],
                "filingDate": ["2026-08-20", "2026-05-20"][:rows],
                "reportDate": ["2026-06-30", "2026-03-31"][:rows],
                "form": ["10-Q", "8-K"][:rows],
                "primaryDocument": ["report.htm", "current.htm"][:rows],
            }
        },
    }
    return json.dumps(values, sort_keys=True).encode()


def _response(payload: bytes, locator: str, media_type: str = "application/json") -> NetworkResponse:
    return NetworkResponse(payload=payload, final_locator=locator, media_type=media_type, fetched_at_utc=FETCHED)


def _discovered(tmp_path: Path, *, rows: int = 2, policy: SupplementalSourcePolicyIR | None = None):
    bound = policy or _policy()
    authority = SupplementalSourceAuthority(bound, tmp_path / "store")
    request = _request(bound)
    receipt = authority.capture_discovery(
        request, lambda locator: _response(_submissions(rows), locator)
    )
    candidates = authority.derive_sec_submission_candidates(receipt)
    candidate_set = authority.candidate_set((receipt,), candidates)
    return authority, receipt, candidates, candidate_set


def _metric_candidate(candidate_id: str, **updates: object) -> MetricCandidate:
    values: dict[str, object] = {
        "candidate_id": candidate_id,
        "concept_or_label": "LongTermDebtNoncurrent",
        "source_kind": "sec_companyfacts",
        "period_type": "INSTANT",
        "period_role": "CURRENT_PRIMARY",
        "freshness_status": "CURRENT",
        "unit": "USD",
        "evidence_ids": (f"evidence.{candidate_id}",),
        "direct": True,
        "dimensions_compatible": True,
        "authority_compatible": True,
        "numeric_value": "100",
        "semantic_metric_id": "long_term_debt",
    }
    values.update(updates)
    return MetricCandidate(**values)


def _period(candidate_id: str, **updates: object) -> PeriodCandidate:
    values: dict[str, object] = {
        "candidate_id": candidate_id,
        "period_start": None,
        "period_end": "2026-06-30",
        "filed_date": "2026-08-01",
        "as_of_date": "2026-08-27",
        "form": "10-Q",
        "cadence_profile_id": "quarterly",
        "current_period_end": "2026-06-30",
        "newer_same_basis_exists": False,
    }
    values.update(updates)
    return PeriodCandidate(**values)


def _event_values(run_id: str, stage: str, status: str = "PASS") -> dict[str, object]:
    return {
        "run_id": run_id,
        "stage": stage,
        "attempt": 1,
        "started_at": "2026-08-27T10:00:00Z",
        "ended_at": "2026-08-27T10:00:01Z",
        "duration_ms": 1000,
        "status": status,
        "network_call_count": 0,
        "capture_bytes": 1,
        "input_sha256s": ("1" * 64,),
        "output_sha256s": ("2" * 64,),
        "diagnostic_codes": (),
    }


def test_h1_001_frozen_ba3_files_byte_identical():
    assert _hash("research_agent/semantic_compiler/source_frontend/contracts.py") == "c37dd7847905f9113e5b50af9ba669cebf06f1520c2099de65cb5e4ce16fda2b"
    assert _hash("research_agent/semantic_compiler/source_frontend/planner.py") == "7cf1eaf4b995fafef3a04d2acdbc62ff5828ca0847d34beacc7e1ea3934455fa"


def test_h1_002_frozen_rfc0010_files_byte_identical():
    expected = {
        "contracts.py": "02fb5c09a6068f6f7d59d867d62feea27282df0ea8a0dc85cef97ae66cbcaa13",
        "ba3_bridge.py": "486f1ee3e4ba7cd2ddc24165e78e22ff562dc954aac6c15a88d2ccaafda990f3",
        "live_receipt.py": "52fbdaa97feca277f7de265d38e2bea74ef0b7408963d3713eab265140bcf8ae",
        "capture_store.py": "e5c8e55579bd2db546fb220e4898761139cab81211d4beb2e83aff20e9a9b19d",
    }
    assert all(_hash(f"research_agent/ba12_live_source/{name}") == digest for name, digest in expected.items())


def test_h1_003_companyfacts_nasdaq_planner_unchanged():
    assert _hash("research_agent/semantic_compiler/source_frontend/registry_binding.py") == "685caf645a68c8276f7d7bbe442c47d5219b34948a71a6d563f2139256df56a1"
    assert _hash("research_agent/semantic_compiler/source_frontend/config/source_adapter_implementations.json") == "0891426ebf15f44a5c824e3245d546b4148b4e28a3e1dbfc0a9fae95c0ee145f"


def test_h1_004_policy_bound_before_network(tmp_path: Path):
    policy = _policy()
    authority = SupplementalSourceAuthority(policy, tmp_path / "store")
    seen: list[str] = []
    authority.capture_discovery(_request(policy), lambda locator: (seen.append(policy.policy_sha256) or _response(_submissions(), locator)))
    assert seen == [policy.policy_sha256]
    with pytest.raises(Exception):
        policy.ticker = "CHANGED"


def test_h1_005_discovery_captured_before_parse(tmp_path: Path):
    policy = _policy()
    authority = SupplementalSourceAuthority(policy, tmp_path / "store")
    receipt = authority.capture_discovery(_request(policy), lambda locator: _response(b"not-json", locator))
    assert authority.store.load_verified(receipt.payload_sha256)[1] == b"not-json"
    with pytest.raises(SupplementalSourceError, match="DISCOVERY_JSON_INVALID"):
        authority.derive_sec_submission_candidates(receipt)


def test_h1_006_discovery_is_deterministic(tmp_path: Path):
    authority, receipt, candidates, first = _discovered(tmp_path)
    second_candidates = authority.derive_sec_submission_candidates(receipt)
    second = authority.candidate_set((receipt,), second_candidates)
    assert candidates == second_candidates and first.set_sha256 == second.set_sha256


def test_h1_007_domain_allowlist_blocks(tmp_path: Path):
    policy = _policy()
    authority = SupplementalSourceAuthority(policy, tmp_path / "store")
    request = DiscoveryRequestIR.create(request_id="blocked", policy_sha256=policy.policy_sha256, source_family_id="sec_primary_document", locator="https://example.com/data.json")
    with pytest.raises(SupplementalSourceError, match="DOMAIN_BLOCKED"):
        authority.capture_discovery(request, lambda locator: _response(b"{}", locator))


def test_h1_008_limits_block(tmp_path: Path):
    policy = _policy(max_candidates=1, max_bytes_per_document=1000)
    authority = SupplementalSourceAuthority(policy, tmp_path / "store")
    receipt = authority.capture_discovery(_request(policy), lambda locator: _response(_submissions(), locator))
    with pytest.raises(SupplementalSourceError, match="CANDIDATE_LIMIT"):
        authority.derive_sec_submission_candidates(receipt)


def test_h1_009_redirect_escape_blocks(tmp_path: Path):
    policy = _policy()
    authority = SupplementalSourceAuthority(policy, tmp_path / "store")
    with pytest.raises(SupplementalSourceError, match="DOMAIN_BLOCKED"):
        authority.capture_discovery(_request(policy), lambda locator: _response(b"{}", "https://evil.invalid/redirect"))


def test_h1_010_selected_children_immutable_before_normalize(tmp_path: Path):
    authority, _, _, candidate_set = _discovered(tmp_path, rows=1)
    evidence = authority.capture_selected(candidate_set, authority.select(candidate_set), lambda locator: _response(b"<html><p>Guidance $42</p></html>", locator, "text/html"))
    artifact, payload = authority.store.load_verified(evidence.capture_receipts[0].payload_sha256)
    path = authority.store.root / artifact.content_addressed_relative_path
    assert payload.startswith(b"<html") and path.stat().st_mode & 0o222 == 0


def test_h1_011_child_ids_stable_across_replay(tmp_path: Path):
    authority, receipt, candidates, _ = _discovered(tmp_path)
    assert candidates == authority.derive_sec_submission_candidates(receipt)


def test_h1_012_replay_has_no_network_surface(tmp_path: Path):
    authority, _, _, candidate_set = _discovered(tmp_path, rows=1)
    evidence = authority.capture_selected(candidate_set, authority.select(candidate_set), lambda locator: _response(b"document", locator, "text/plain"))
    assert "fetcher" not in inspect.signature(authority.replay).parameters
    assert authority.replay(candidate_set, evidence.capture_receipts).capture_receipts == evidence.capture_receipts


def test_h1_013_live_and_replay_evidence_hash_identical(tmp_path: Path):
    authority, _, _, candidate_set = _discovered(tmp_path, rows=1)
    live = authority.capture_selected(candidate_set, authority.select(candidate_set), lambda locator: _response(b"document", locator, "text/plain"))
    replay = authority.replay(candidate_set, live.capture_receipts)
    assert replay.evidence_set_sha256 == live.evidence_set_sha256


def test_h1_014_document_normalization_deterministic():
    kwargs = dict(document_id="doc", accession_number="1", report_date="2026-06-30", filing_date="2026-08-01", document_name="report.htm", media_type="text/html")
    payload = b"<html><body><p>Net production 4.2</p><table><tr><th>A</th><td>1</td></tr></table></body></html>"
    assert normalize_document(payload, **kwargs) == normalize_document(payload, **kwargs)


def test_h1_015_ambiguous_numeric_cannot_be_trusted():
    with pytest.raises(ValueError):
        DocumentObservationIR.create(source_document_sha256="0" * 64, locator_type="text_span", locator="block:0", reported_label="guidance", raw_value_text="10 | 20", parsed_numeric_value_or_null="10", reported_unit_text_or_null=None, reported_period_text_or_null=None, reported_basis_text_or_null=None, context_text="guidance 10 to 20", ambiguity_codes=("NUMERIC_CARDINALITY_NOT_ONE",), trusted_numeric=True)


def test_h1_016_source_layer_has_no_issuer_specific_rules():
    source = inspect.getsource(SupplementalSourceAuthority)
    assert not any(value in source for value in ("CRM", "PLD", "JPM", "XOM", "NOW", "BAC", "CVX"))


def test_h1_021_structured_regulatory_profile_and_fixture_compile():
    fixture = json.loads((ROOT / "research_agent/alpha_shared/config/structured_regulatory_fixture_v1.json").read_text())
    assert STRUCTURED_REGULATORY_SOURCE_PROFILE["live_activation"] is False
    assert fixture["source_family_id"] == "structured_regulatory_dataset"


def test_h2_001_resolver_has_zero_issuer_branches():
    source = inspect.getsource(resolve_metric)
    assert not any(value in source for value in ("ticker", "issuer", "NOW", "BAC", "CVX"))


def test_h2_002_resolution_receipt_deterministic():
    candidate = _metric_candidate("a")
    assert resolve_metric("long_term_debt", (candidate,)).receipt_sha256 == resolve_metric("long_term_debt", (candidate,)).receipt_sha256


def test_h2_003_now_stale_debt_non_primary():
    result = resolve_metric("long_term_debt", (_metric_candidate("now-old", freshness_status="STALE", period_role="HISTORICAL"),))
    assert result.status == "STALE_ONLY" and result.selected_candidate_id_or_null is None


def test_h2_004_o_debt_explicit_stale_only():
    result = resolve_metric("long_term_debt", (_metric_candidate("o-old", concept_or_label="LongTermDebtAndFinanceLeaseObligationsNoncurrent", freshness_status="STALE"),))
    assert result.status == "STALE_ONLY"


def test_h2_005_bac_net_revenue_explicit_unsupported():
    assert resolve_metric("net_revenue", ()).status == "UNSUPPORTED"


def test_h2_006_bac_debt_explicit_unsupported():
    assert resolve_metric("long_term_debt", ()).status == "UNSUPPORTED"


def test_h2_007_cvx_capex_explicit_unsupported():
    assert resolve_metric("capital_expenditure", ()).status == "UNSUPPORTED"


def test_h2_008_cvx_cash_stale_only():
    candidate = _metric_candidate("cvx-old", concept_or_label="CashAndCashEquivalentsAtCarryingValue", semantic_metric_id="cash_and_equivalents", freshness_status="STALE")
    assert resolve_metric("cash_and_equivalents", (candidate,)).status == "STALE_ONLY"


def test_h2_009_numeric_similarity_never_creates_synonym():
    wrong = _metric_candidate("wrong", concept_or_label="Assets", numeric_value="100")
    assert resolve_metric("long_term_debt", (wrong,)).status == "UNSUPPORTED"


def test_h2_010_stale_never_beats_current():
    stale = _metric_candidate("a-stale", freshness_status="STALE")
    current = _metric_candidate("b-current")
    assert resolve_metric("long_term_debt", (stale, current)).selected_candidate_id_or_null == "b-current"


def test_h2_011_equal_top_candidates_are_ambiguous():
    assert resolve_metric("long_term_debt", (_metric_candidate("a"), _metric_candidate("b"))).status == "AMBIGUOUS"


def test_h3_001_now_old_debt_stale():
    receipt = classify_period(_period("now", period_end="2021-12-31", current_period_end="2026-06-30"))
    assert receipt.freshness_status == "STALE" and receipt.comparative_role != "CURRENT_PRIMARY"


def test_h3_002_o_old_debt_stale():
    assert classify_period(_period("o", period_end="2012-12-31", current_period_end="2026-06-30")).freshness_status == "STALE"


def test_h3_003_jpm_q2_and_h1_distinct():
    quarter = classify_period(_period("q2", period_start="2026-04-01"))
    ytd = classify_period(_period("h1", period_start="2026-01-01"))
    assert quarter.duration_role == "STANDALONE_QUARTER" and ytd.duration_role == "YEAR_TO_DATE"


def test_h3_004_xom_refiled_prior_period_comparative():
    receipt = classify_period(_period("xom-prior", period_start="2025-04-01", period_end="2025-06-30", filed_date="2026-08-01", current_period_end="2026-06-30"))
    assert receipt.comparative_role == "COMPARATIVE"


def test_h3_005_cvx_stale_cash_excluded_primary():
    receipt = classify_period(_period("cvx-cash", period_end="2024-12-31", current_period_end="2026-06-30"))
    assert receipt.freshness_status == "STALE" and receipt.comparative_role != "CURRENT_PRIMARY"


def test_h3_006_recent_filing_does_not_make_old_period_current():
    receipt = classify_period(_period("old", period_end="2020-12-31", filed_date="2026-08-26", current_period_end="2026-06-30"))
    assert receipt.freshness_status == "STALE" and receipt.comparative_role == "COMPARATIVE"


def test_h3_007_incompatible_periods_block_derived_metric():
    quarter = classify_period(_period("q2", period_start="2026-04-01"))
    ytd = classify_period(_period("h1", period_start="2026-01-01"))
    assert not derived_inputs_compatible((quarter, ytd))


def test_h4_001_append_only_chain_verifies(tmp_path: Path):
    ledger = OperationsLedger(tmp_path / "ops.jsonl")
    ledger.append(**_event_values("run", "capture"))
    ledger.append(**_event_values("run", "compile"))
    assert len(ledger.verify()) == 2


def test_h4_002_crash_is_detectable_incomplete_run(tmp_path: Path):
    ledger = OperationsLedger(tmp_path / "ops.jsonl")
    ledger.append(**_event_values("run", "capture", "STARTED"))
    assert ledger.aggregate()["incomplete_runs"] == 1


def test_h4_003_recovery_appends_history(tmp_path: Path):
    ledger = OperationsLedger(tmp_path / "ops.jsonl")
    first = ledger.append(**_event_values("run", "capture", "STARTED"))
    ledger.append(**_event_values("run", "recovery", "RECOVERED"))
    assert ledger.verify()[0].event_sha256 == first.event_sha256


def test_h4_004_tampered_prior_event_blocks(tmp_path: Path):
    ledger = OperationsLedger(tmp_path / "ops.jsonl")
    ledger.append(**_event_values("run", "capture"))
    payload = ledger.path.read_text().replace('"capture_bytes":1', '"capture_bytes":2')
    ledger.path.write_text(payload)
    with pytest.raises(OperationsLedgerError, match="OPS_LEDGER_INVALID"):
        ledger.verify()


def test_h4_005_out_of_order_sequence_blocks(tmp_path: Path):
    ledger = OperationsLedger(tmp_path / "ops.jsonl")
    with pytest.raises(OperationsLedgerError, match="OPS_SEQUENCE_INVALID"):
        ledger.append(**_event_values("run", "capture"), sequence=2)


def test_h4_006_aggregate_is_deterministic(tmp_path: Path):
    ledger = OperationsLedger(tmp_path / "ops.jsonl")
    ledger.append(**_event_values("run", "complete"))
    assert ledger.aggregate() == ledger.aggregate()


def test_h4_007_replay_network_calls_block_batch(tmp_path: Path):
    ledger = OperationsLedger(tmp_path / "ops.jsonl")
    values = _event_values("run", "offline_replay")
    values["network_call_count"] = 1
    ledger.append(**values)
    with pytest.raises(OperationsLedgerError, match="OPS_REPLAY_NETWORK_CALLS"):
        verify_batch_gate(ledger.aggregate())


def test_h4_008_manual_semantic_intervention_blocks_batch(tmp_path: Path):
    ledger = OperationsLedger(tmp_path / "ops.jsonl")
    values = _event_values("run", "resolve")
    values["manual_semantic_intervention_count"] = 1
    ledger.append(**values)
    with pytest.raises(OperationsLedgerError, match="OPS_MANUAL_SEMANTIC_INTERVENTION"):
        verify_batch_gate(ledger.aggregate())


def test_h4_concurrent_append_lock_serializes_writers(tmp_path: Path):
    ledger = OperationsLedger(tmp_path / "ops.jsonl")
    with ThreadPoolExecutor(max_workers=4) as pool:
        events = list(pool.map(lambda index: ledger.append(**_event_values("run", f"stage-{index}")), range(8)))
    assert len(events) == 8
    assert [item.sequence for item in ledger.verify()] == list(range(1, 9))
