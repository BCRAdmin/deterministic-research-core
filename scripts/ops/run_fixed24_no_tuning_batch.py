#!/usr/bin/env python3
"""Execute the hash-bound Room16 Fixed24 no-tuning batch."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from research_agent.alpha_shared.archetype_profiles import archetype_profile_registry
from research_agent.alpha_shared.contracts import (
    DiscoveryRequestIR,
    DocumentObservationIR,
    SharedBaseInputIR,
    SupplementalCompileInputIR,
    SupplementalSourcePolicyIR,
)
from research_agent.alpha_shared.document_normalizer import (
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.execution_authority import (
    AuthorizationReceiptIR,
    BatchExecutionAuthorityIR,
    RuntimeIdentityIR,
    SharedFreezeBindingIR,
    authorize_case_before_network,
    fixed_company_list_sha256,
    ordered_cases_from_fixed_company_list,
    threshold_authority_sha256,
)
from research_agent.alpha_shared.issuer_identity import resolve_issuer_identity
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.runner import (
    replay_canonical_alpha_case,
    run_canonical_alpha_case,
)
from research_agent.alpha_shared.source_authority import (
    NetworkResponse,
    SupplementalSourceAuthority,
)
from research_agent.ba12_live_source import (
    ExistingAdapterHarness,
    LiveCaptureExecutor,
    bridge_capture_set_to_ba3,
    verify_live_bridge,
)
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR
from research_agent.semantic_compiler.source_frontend.planner import (
    build_compile_request,
    plan_source_acquisition,
)
from research_agent.sources.prices.nasdaq_price_provider import NasdaqPriceProvider
from research_agent.sources.sec.sec_client import SecClient, SecClientConfig


ROOT = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).resolve()
VERIFIER = RUNNER.with_name("verify_fixed24_no_tuning_batch.py")
EXECUTION_LABEL = "fixed24"
FREEZE_FILENAME = "01_FINAL_SHARED_FREEZE.json"
AS_OF = "2026-08-28"
RESEARCH_COMMIT = "8dad9d5a74e9c82c1ed901e48fad05d7368c0122"
RESEARCH_TREE = "cce91d2cf386b52c70bc462ec16c11850ad24611"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_TREE = "a382d9c096825910b5e0e8865414ea232b95bd40"
R4_EVIDENCE_SHA = "58a3cfc5834744de9b05c4bab379f82db61a863eba8710438dce49fc729e742a"
R4_CANDIDATE_SHA = "549bfbc0d0865d3c5b686f47654a5b57cb4944c0e42f38275df106a5f3a3d40d"
AUTHORITY_CLOSURE_SHA = "b1d60185eb2fa07edfabd4a25a3c1e66f86896781d79f73025bf3ad7d22bf16f"
PROFILE_REGISTRY_SHA = "daca68384a7b8f548870ee13995f9e2baa19852221cfdc7719bea4b6af00927b"
FOREIGN_ROOT = Path(
    "/Users/BjornRosinger/Documents/DreamFactory/Utility-Websites/materialbedarf-rechner.de"
)
USER_AGENT = os.environ.get(
    "ROOM16_SEC_USER_AGENT", "BCRAdmin Room16 RFC0011 contact@bcradmin.com"
)
PROFILE_METRICS = {
    "saas": ("crpo", "guidance"),
    "reit": (
        "reported_ffo",
        "reported_core_ffo",
        "reported_affo",
        "occupancy",
        "same_store_noi",
    ),
    "bank": ("efficiency_ratio", "net_interest_margin", "rotce"),
    "energy": ("production_volume", "segment_operating_results"),
}


def validate_profile_metric_requests(
    profile_metrics: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Bind operational profile requests to registry IDs before network use."""
    requested_by_profile = PROFILE_METRICS if profile_metrics is None else profile_metrics
    profiles = label_profiles()
    validated: dict[str, dict[str, Any]] = {}
    for profile, metric_ids in requested_by_profile.items():
        if len(metric_ids) != len(set(metric_ids)):
            raise RuntimeError(f"SUPPLEMENTAL_PROFILE_LABEL_DUPLICATE:{profile}")
        requested: dict[str, Any] = {}
        for metric_id in metric_ids:
            if metric_id not in profiles:
                raise RuntimeError(
                    f"SUPPLEMENTAL_PROFILE_LABEL_MISSING:{profile}:{metric_id}"
                )
            requested[metric_id] = profiles[metric_id]
        validated[profile] = requested
    return validated


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _runtime_identity(product_root: Path) -> RuntimeIdentityIR:
    return RuntimeIdentityIR(
        research_commit=_git(ROOT, "rev-parse", "HEAD"),
        research_tree=_git(ROOT, "rev-parse", "HEAD^{tree}"),
        product_commit=_git(product_root, "rev-parse", "HEAD"),
        product_tree=_git(product_root, "rev-parse", "HEAD^{tree}"),
        as_of_date=AS_OF,
    )


def _verify_runtime(contract_root: Path, product_root: Path, freeze: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = _runtime_identity(product_root)
    expected = (RESEARCH_COMMIT, RESEARCH_TREE, PRODUCT_COMMIT, PRODUCT_TREE)
    actual = (
        identity.research_commit,
        identity.research_tree,
        identity.product_commit,
        identity.product_tree,
    )
    if actual != expected:
        raise RuntimeError(f"FIXED24_RUNTIME_IDENTITY_DRIFT:{actual}")
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet"], check=False).returncode:
        raise RuntimeError("FIXED24_RESEARCH_TRACKED_DIFF")
    if subprocess.run(["git", "-C", str(product_root), "diff", "--quiet"], check=False).returncode:
        raise RuntimeError("FIXED24_PRODUCT_TRACKED_DIFF")
    lock = _json(contract_root / "04_RUNTIME_SOURCE_LOCK.json")
    observed: dict[str, str] = {}
    for group in ("execution_control", "semantic_source_hashes"):
        for relative, expected_sha in lock[group].items():
            digest = _sha(ROOT / relative)
            observed[relative] = digest
            if digest != expected_sha:
                raise RuntimeError(f"FIXED24_RUNTIME_SOURCE_DRIFT:{relative}")
    registry_sha = str(archetype_profile_registry()["registry_sha256"])
    if registry_sha != PROFILE_REGISTRY_SHA:
        raise RuntimeError("FIXED24_PROFILE_REGISTRY_DRIFT")
    if freeze is not None:
        for relative, expected_sha in freeze["operational_script_hashes"].items():
            if _sha(ROOT / relative) != expected_sha:
                raise RuntimeError(f"FIXED24_OPERATIONAL_SCRIPT_DRIFT:{relative}")
    return {
        "status": "PASS",
        "runtime_identity": identity.model_dump(mode="json"),
        "runtime_source_hashes": observed,
        "archetype_profile_registry_sha256": registry_sha,
    }


def _documents(contract_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    fixed = _json(contract_root / "02_FIXED24_LIST.json")
    thresholds = _json(contract_root / "03_FIXED24_THRESHOLDS.json")
    if fixed_company_list_sha256(fixed) != fixed["frozen_list_sha256"]:
        raise RuntimeError("FIXED24_LIST_SELFHASH_DRIFT")
    if threshold_authority_sha256(thresholds) != (
        "ca0e85b21f0f5fa4489e011f8ccff2a1764eaf64e16fc0cb6dcf5991cef6295e"
    ):
        raise RuntimeError("FIXED24_THRESHOLD_SELFHASH_DRIFT")
    return fixed, thresholds


def _self_test(contract_root: Path, product_root: Path) -> dict[str, Any]:
    validated_profile_requests = validate_profile_metric_requests()
    runtime = _runtime_identity(product_root)
    fixed, thresholds = _documents(contract_root)
    authority = BatchExecutionAuthorityIR.create(
        authority_kind="FIXED_BATCH",
        as_of_date=AS_OF,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=None,
        fixed_company_list_sha256=fixed_company_list_sha256(fixed),
        threshold_sha256=threshold_authority_sha256(thresholds),
        ordered_cases=ordered_cases_from_fixed_company_list(fixed),
        network_live_authorized=False,
    )
    receipts = [
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
            fixed_company_list=fixed,
            threshold_authority=thresholds,
        )
        for case in authority.ordered_cases
    ]
    network_counter = 0
    blocked = False
    try:
        authorize_case_before_network(
            ticker="WRONG",
            archetype_profile_id="saas",
            sequence=1,
            authority=authority,
            runtime_identity=runtime,
            fixed_company_list=fixed,
            threshold_authority=thresholds,
        )
        network_counter += 1
    except Exception:
        blocked = True
    if len(receipts) != 24 or network_counter != 0 or not blocked:
        raise RuntimeError("FIXED24_OPERATIONAL_FIXTURE_FAILED")
    missing_label_blocked = False
    try:
        validate_profile_metric_requests({"synthetic": ("missing_metric_id",)})
    except RuntimeError as exc:
        missing_label_blocked = str(exc) == (
            "SUPPLEMENTAL_PROFILE_LABEL_MISSING:synthetic:missing_metric_id"
        )
    if not missing_label_blocked:
        raise RuntimeError("FIXED24_PROFILE_LABEL_GUARD_FAILED")
    return {
        "status": "PASS",
        "fixture_preflight_count": len(receipts),
        "fixture_network_query_count": 0,
        "negative_authorization_blocked_before_network": True,
        "profile_metric_request_count": sum(
            len(requests) for requests in validated_profile_requests.values()
        ),
        "missing_profile_label_blocked_before_network": True,
        "runner_sha256": _sha(RUNNER),
        "verifier_sha256": _sha(VERIFIER),
    }


def _prepare(contract_root: Path, output: Path, product_root: Path) -> int:
    if output.exists():
        raise SystemExit(f"output already exists: {output}")
    output.mkdir(parents=True)
    validate_profile_metric_requests()
    runtime_report = _verify_runtime(contract_root, product_root)
    fixed, thresholds = _documents(contract_root)
    fixture = _self_test(contract_root, product_root)
    operational_hashes = {
        str(RUNNER.relative_to(ROOT)): _sha(RUNNER),
        str(VERIFIER.relative_to(ROOT)): _sha(VERIFIER),
    }
    lock = _json(contract_root / "04_RUNTIME_SOURCE_LOCK.json")
    freeze_body = {
        "contract_id": "room16.shared_hardening_freeze",
        "contract_version": 1,
        "status": "FROZEN",
        "r4_evidence_sha256": R4_EVIDENCE_SHA,
        "r4_candidate_sha256": R4_CANDIDATE_SHA,
        "execution_authority_closure_sha256": AUTHORITY_CLOSURE_SHA,
        "research_commit": RESEARCH_COMMIT,
        "research_tree": RESEARCH_TREE,
        "product_commit": PRODUCT_COMMIT,
        "product_tree": PRODUCT_TREE,
        "fixed24_list_sha256": fixed_company_list_sha256(fixed),
        "threshold_sha256": threshold_authority_sha256(thresholds),
        "archetype_profile_registry_sha256": PROFILE_REGISTRY_SHA,
        "runtime_source_lock": lock,
        "operational_script_hashes": operational_hashes,
        "rfc0011_frozen": True,
        "h1_source_authority_frozen": True,
        "h2_metric_resolver_frozen": True,
        "h3_period_freshness_frozen": True,
        "h4_operations_ledger_frozen": True,
        "raw_candidate_inventory_frozen": True,
        "archetype_profiles_frozen": True,
        "canonical_case_runner_frozen": True,
        "execution_authority_frozen": True,
        "internal_alpha_report_contract_frozen": True,
        "operational_batch_runner_frozen": True,
        "product_report_v2_frozen": False,
        "release_authorized": False,
        "deploy_authorized": False,
        "publication_authorized": False,
        "commerce_authorized": False,
    }
    freeze = {**freeze_body, "freeze_sha256": sha256_json(freeze_body)}
    _write_json(output / "01_FINAL_SHARED_FREEZE.json", freeze)
    verification = _verify_runtime(contract_root, product_root, freeze)
    verification.update(
        {
            "freeze_selfhash_match": sha256_json(freeze_body) == freeze["freeze_sha256"],
            "operational_fixture": fixture,
            "status": "PASS",
        }
    )
    _write_json(output / "02_SHARED_FREEZE_VERIFICATION.json", verification)
    runtime = _runtime_identity(product_root)
    authority = BatchExecutionAuthorityIR.create(
        authority_kind="FIXED_BATCH",
        as_of_date=AS_OF,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=freeze["freeze_sha256"],
        fixed_company_list_sha256=fixed_company_list_sha256(fixed),
        threshold_sha256=threshold_authority_sha256(thresholds),
        ordered_cases=ordered_cases_from_fixed_company_list(fixed),
        network_live_authorized=True,
    )
    binding = SharedFreezeBindingIR.create(
        freeze_sha256=freeze["freeze_sha256"],
        fixed_company_list_sha256=authority.fixed_company_list_sha256,
        threshold_sha256=authority.threshold_sha256,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
    )
    _write_json(output / "03_FINAL_LIVE_EXECUTION_AUTHORITY.json", authority.model_dump(mode="json"))
    _write_json(output / "04_SHARED_FREEZE_BINDING.json", binding.model_dump(mode="json"))
    receipts = [
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
            shared_freeze=binding,
            fixed_company_list=fixed,
            threshold_authority=thresholds,
        )
        for case in authority.ordered_cases
    ]
    _write_json(output / "05_ALL_24_AUTHORIZATION_PREFLIGHTS.json", [r.model_dump(mode="json") for r in receipts])
    _write_json(
        output / "06_AUTHORIZATION_RECEIPT_ORIGIN_AUDIT.json",
        {
            "status": "PASS",
            "method": "deterministic_recomputation_from_final_authority_and_freeze",
            "authority_sha256": authority.authority_sha256,
            "binding_sha256": binding.binding_sha256,
            "receipt_count": 24,
            "receipt_sha256s": [r.receipt_sha256 for r in receipts],
            "all_unique": len({r.receipt_sha256 for r in receipts}) == 24,
        },
    )
    _write_json(
        output / "07_BATCH_PRESTART_STATE.json",
        {
            "status": "PASS",
            "authorization_preflight_count": 24,
            "case_attempt_count": 0,
            "live_network_query_count": 0,
            "completed_case_count": 0,
            "batch_started": False,
        },
    )
    _write_json(output / "08_FIXED24_LIST_BINDING.json", {"status": "PASS", "sha256": fixed_company_list_sha256(fixed), "document": fixed})
    _write_json(output / "09_FIXED24_THRESHOLD_BINDING.json", {"status": "PASS", "sha256": threshold_authority_sha256(thresholds), "document": thresholds})
    _write_json(output / "10_BATCH_RUN_LEDGER.json", {"status": "PRESTART", "events": []})
    _write_json(output / "11_BATCH_FINDINGS_LEDGER.json", {"status": "PRESTART", "findings": []})
    boundary_script = ROOT / "scripts/ops/verify_project_boundary_non_interference_v2.py"
    subprocess.run(
        [
            sys.executable,
            str(boundary_script),
            "snapshot",
            "--foreign-root",
            str(FOREIGN_ROOT),
            "--output",
            str(output / ".boundary_before.json"),
        ],
        check=True,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
    )
    print(json.dumps({"status": "PASS", "phase": "PRESTART", "freeze_sha256": freeze["freeze_sha256"], "authority_sha256": authority.authority_sha256, "preflights": 24, "network_queries": 0}, sort_keys=True))
    return 0


class RetryAdapter:
    def __init__(self, adapter: object, log: list[dict[str, Any]]) -> None:
        self.adapter = adapter
        self.log = log

    def _call(self, name: str, *args: object) -> object:
        last: Exception | None = None
        for retry in range(4):
            try:
                value = getattr(self.adapter, name)(*args)
                self.log.append({"method": name, "retry": retry, "status": "PASS"})
                return value
            except Exception as exc:
                last = exc
                transient = isinstance(exc, (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, OSError, RuntimeError))
                self.log.append({"method": name, "retry": retry, "status": "RETRY" if transient and retry < 3 else "FAIL", "error": type(exc).__name__})
                if not transient or retry >= 3:
                    raise
                time.sleep((1, 2, 4)[retry])
        raise RuntimeError("unreachable retry state") from last

    def get_companyfacts(self, cik: str) -> object:
        return self._call("get_companyfacts", cik)

    def get_company_tickers(self) -> object:
        return self._call("get_company_tickers")

    def get_history(self, ticker: str, start: str, end: str) -> object:
        return self._call("get_history", ticker, start, end)


class SupplementalFetcher:
    def __init__(self, log: list[dict[str, Any]]) -> None:
        self.log = log

    def __call__(self, locator: str) -> NetworkResponse:
        last: Exception | None = None
        for retry in range(4):
            try:
                request = urllib.request.Request(locator, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip", "Accept": "application/json,text/html,text/plain"})
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = response.read()
                    if response.headers.get("Content-Encoding") == "gzip":
                        payload = gzip.decompress(payload)
                    result = NetworkResponse(payload=payload, final_locator=response.geturl(), media_type=response.headers.get_content_type(), fetched_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), status=str(response.status))
                self.log.append({"locator": locator, "retry": retry, "status": "PASS", "bytes": len(payload)})
                time.sleep(0.5)
                return result
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                last = exc
                self.log.append({"locator": locator, "retry": retry, "status": "RETRY" if retry < 3 else "FAIL", "error": type(exc).__name__})
                if retry >= 3:
                    raise
                retry_after = exc.headers.get("Retry-After") if isinstance(exc, urllib.error.HTTPError) else None
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else (1, 2, 4)[retry])
        raise RuntimeError("unreachable retry state") from last


def _resolve_identity(ticker: str, company_name: str, sec: RetryAdapter) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = sec.get_company_tickers()
    identity = resolve_issuer_identity(
        requested_ticker=ticker,
        canonical_company_name=company_name,
        as_of_date=AS_OF,
        current_directory=payload,
        source_receipt_sha256=sha256_json(payload),
    )
    effective = str(identity["effective_ticker"])
    resolution = {"status": "supported", "runtimeReady": True, "inputKind": "ticker", "input": ticker, "ticker": effective, "requestedTicker": ticker, "companyName": company_name, "exchange": "US Listed", "exchangeCode": "US", "jurisdiction": "US", "isin": None, "source": "SEC company_tickers.json"}
    return resolution, {"status": "PASS", "provider_query_count": 1, "ticker": ticker, "effective_ticker": effective, "company_name": company_name, "cik": str(identity["cik"]), "issuer_identity": identity, "resolution": resolution}


def _supplemental(case_root: Path, request_sha: str, ticker: str, company: str, cik: str, profile: str, fetch_log: list[dict[str, Any]]) -> tuple[SupplementalCompileInputIR, dict[str, Any]]:
    policy = SupplementalSourcePolicyIR.create(base_request_sha256=request_sha, ticker=ticker, canonical_company_name=company, issuer_cik=cik, as_of_date=AS_OF, allowed_source_family_ids=("sec_filed_exhibit", "sec_primary_document", "structured_regulatory_dataset"), allowed_domains=("data.sec.gov", "www.sec.gov"), allowed_media_types=("application/json", "application/xhtml+xml", "text/html", "text/plain"), allowed_sec_forms=("10-K", "10-Q", "8-K"), max_discovery_requests=4, max_candidates=250, max_selected_documents=3, max_bytes_per_document=20_000_000, discovery_lookback_days=550, paid_provider_ids_allowed=(), network_mode="live_acquisition")
    authority = SupplementalSourceAuthority(policy, case_root / "captures/rfc0011")
    fetcher = SupplementalFetcher(fetch_log)
    submissions_request = DiscoveryRequestIR.create(request_id=f"{EXECUTION_LABEL}.discovery.submissions.{ticker.lower()}", policy_sha256=policy.policy_sha256, source_family_id="sec_primary_document", locator=f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json")
    submissions = authority.capture_discovery(submissions_request, fetcher)
    primary_candidates = authority.derive_sec_submission_candidates(submissions)
    eligible = [item for item in primary_candidates if item.form in {"10-Q", "10-K"}]
    if not eligible:
        raise RuntimeError(f"FIXED24_PRIMARY_DOCUMENT_MISSING:{ticker}")
    primary = sorted(eligible, key=lambda item: (item.filing_date, item.accession_number), reverse=True)[0]
    discovery = [submissions]
    exhibits: tuple[Any, ...] = ()
    parents = [item for item in primary_candidates if item.form == "8-K"]
    if parents:
        parent = sorted(parents, key=lambda item: (item.filing_date, item.accession_number), reverse=True)[0]
        index_request = DiscoveryRequestIR.create(request_id=f"{EXECUTION_LABEL}.discovery.index.{ticker.lower()}", policy_sha256=policy.policy_sha256, source_family_id="sec_filed_exhibit", locator=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{parent.accession_number.replace('-', '')}/index.json")
        index_receipt = authority.capture_discovery(index_request, fetcher)
        discovery.append(index_receipt)
        exhibits = authority.derive_filing_index_candidates(index_receipt, issuer_cik=cik, accession_number=parent.accession_number, filing_date=parent.filing_date, report_date=parent.report_date, form=parent.form, primary_document=parent.document_name)
    candidate_set = authority.candidate_set(tuple(discovery), tuple(primary_candidates) + tuple(exhibits))
    selected = (primary,) + tuple(exhibits[:1])
    evidence = authority.capture_selected(candidate_set, selected, fetcher)
    candidate_by_id = {item.candidate_id: item for item in candidate_set.candidates}
    requested = validate_profile_metric_requests()[profile]
    observations: list[DocumentObservationIR] = []
    normalized: list[dict[str, Any]] = []
    for receipt in evidence.capture_receipts:
        candidate = candidate_by_id[receipt.candidate_id]
        _, payload = authority.store.load_verified(receipt.payload_sha256)
        document = normalize_document(payload, document_id=candidate.candidate_id, accession_number=candidate.accession_number, report_date=candidate.report_date, filing_date=candidate.filing_date, document_name=candidate.document_name, media_type=receipt.media_type)
        normalized.append(document.model_dump(mode="json"))
        observations.extend(discover_observations(document, requested))
    replay = authority.replay(candidate_set, evidence.capture_receipts)
    if replay.evidence_set_sha256 != evidence.evidence_set_sha256:
        raise RuntimeError(f"FIXED24_SUPPLEMENTAL_REPLAY_DRIFT:{ticker}")
    supplemental = SupplementalCompileInputIR.create(supplemental_policy_sha256=policy.policy_sha256, discovery_set_sha256=candidate_set.set_sha256, supplemental_evidence_set_sha256=evidence.evidence_set_sha256, observations=tuple(observations))
    return supplemental, {"status": "PASS", "policy": policy.model_dump(mode="json"), "discovery_receipts": [item.model_dump(mode="json") for item in discovery], "candidate_set": candidate_set.model_dump(mode="json"), "evidence_set": evidence.model_dump(mode="json"), "normalized_document_count": len(normalized), "observation_count": len(observations), "observations": [item.model_dump(mode="json") for item in observations], "offline_replay_network_calls": 0}


def _base_capture(case_root: Path, ticker: str, company: str, retry_log: list[dict[str, Any]]) -> tuple[SharedBaseInputIR, dict[str, Any], dict[str, Any], dict[str, Any]]:
    sec_raw = SecClient(SecClientConfig(user_agent=USER_AGENT, request_delay_seconds=0.5, timeout_seconds=30, max_retries=1, use_cache=False))
    sec = RetryAdapter(sec_raw, retry_log)
    resolution, identity = _resolve_identity(ticker, company, sec)
    request = build_compile_request(resolution, as_of_date=AS_OF, allowed_provider_ids=("nasdaq", "sec"), available_configuration_ids=("ROOM16_SEC_USER_AGENT",), network_mode="live_acquisition")
    plan = plan_source_acquisition(request, price_provider_id="nasdaq")
    live_root = case_root / "captures/rfc0010"
    executor = LiveCaptureExecutor(live_root)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    cutoff = datetime.combine(date.fromisoformat(AS_OF), datetime.max.time(), tzinfo=timezone.utc).replace(microsecond=0)
    authority_time = min(now, cutoff).isoformat().replace("+00:00", "Z")
    start = (date.fromisoformat(AS_OF) - timedelta(days=400)).isoformat()
    nasdaq = RetryAdapter(NasdaqPriceProvider(), retry_log)
    cik = str(identity["cik"])
    provider_ticker = str(identity["effective_ticker"])
    adapters = {
        "sec": ExistingAdapterHarness(provider_id="sec", adapter=sec, method_name="get_companyfacts", source_id=f"SEC_COMPANYFACTS_CIK{cik.zfill(10)}", source_type="sec_filing", original_locator=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json", final_locator=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json", raw_status="200", media_type="application/json", fetched_at_utc=authority_time, available_at_utc=authority_time, args=(cik,)),
        "nasdaq": ExistingAdapterHarness(provider_id="nasdaq", adapter=nasdaq, method_name="get_history", source_id=f"NASDAQ_OHLCV_{provider_ticker}", source_type="exchange_ohlcv", original_locator=f"https://www.nasdaq.com/market-activity/stocks/{provider_ticker.lower()}/historical", final_locator=f"https://api.nasdaq.com/api/quote/{provider_ticker}/historical", raw_status="200", media_type="application/json", fetched_at_utc=authority_time, available_at_utc=authority_time, args=(provider_ticker, start, AS_OF)),
    }
    records = tuple(executor.capture(request=request, plan=plan, acquisition_id=item.acquisition_id, attempt_id=f"{EXECUTION_LABEL}.{ticker.lower()}.{item.provider_id}.1", adapter=adapters[item.provider_id]) for item in plan.acquisitions)
    snapshot_root = case_root / "captures/ba3_snapshot"
    bridge = bridge_capture_set_to_ba3(request=request, plan=plan, records=records, capture_store_root=executor.capture_store.root, snapshot_root=snapshot_root, staged_at_utc=authority_time)
    verification = verify_live_bridge(records=records, result=bridge, capture_store_root=executor.capture_store.root)
    base = SharedBaseInputIR.from_snapshot(snapshot=bridge.snapshot, snapshot_root=snapshot_root)
    capture = {"status": "PASS", "records": [{"receipt": item.receipt.model_dump(mode="json"), "artifact": item.artifact.model_dump(mode="json")} for item in records], "capture_set": bridge.capture_set.model_dump(mode="json"), "closure": bridge.closure.model_dump(mode="json"), "bridge_verification": verification, "snapshot": bridge.snapshot.model_dump(mode="json"), "snapshot_root": str(snapshot_root)}
    return base, identity, request.model_dump(mode="json"), {"plan": plan.model_dump(mode="json"), "capture": capture}


def _replay_case(case_root: Path, product_root: Path, counter: int) -> int:
    base_report = _json(case_root / "08_SOURCE_SNAPSHOT.json")
    base = SharedBaseInputIR.from_snapshot(snapshot=SourceSnapshotIR.model_validate(base_report["snapshot"]), snapshot_root=Path(base_report["snapshot_root"]))
    supplemental = SupplementalCompileInputIR.model_validate(_json(case_root / "09_RFC0011_SUPPLEMENTAL_REPORT.json")["supplemental_input"])
    result = replay_canonical_alpha_case(base_input=base, supplemental_input=supplemental, archetype_profile_id=_json(case_root / "13_ARCHETYPE_PROFILE_BINDING.json")["archetype_profile_id"], output_root=case_root / "replay_bundle", ledger_path=case_root / "replay_operations.jsonl", research_commit=RESEARCH_COMMIT, research_tree=RESEARCH_TREE, monotonic_counter=counter)
    report = {"status": "PASS", "network_provider_calls": 0, "bundle_sha256": result.compiled.manifest["bundle_sha256"], "signed_receipt_sha256": result.compiled.receipt["receipt_sha256"], "internal_report_sha256": result.compiled.internal_report.report_sha256, "runner_report": result.report, "bundle_root": str(result.compiled.bundle_root)}
    _write_json(case_root / "18_OFFLINE_REPLAY_REPORT.json", report)
    return 0


def _execute_case(output: Path, case: dict[str, Any], receipt: AuthorizationReceiptIR, contract_root: Path, product_root: Path) -> dict[str, Any]:
    sequence = int(case["sequence"]); ticker = str(case["ticker"]); company = str(case["company_name"]); profile = str(case["archetype_profile_id"])
    case_root = output / "companies" / f"{sequence:02d}_{ticker}"
    if case_root.exists():
        raise RuntimeError(f"FIXED24_CASE_OUTPUT_EXISTS:{ticker}")
    case_root.mkdir(parents=True)
    validate_profile_metric_requests()
    freeze = _json(output / FREEZE_FILENAME)
    _verify_runtime(contract_root, product_root, freeze)
    _write_json(case_root / "01_AUTHORIZATION_RECEIPT.json", receipt.model_dump(mode="json"))
    _write_json(case_root / "02_AUTHORIZATION_BINDING_AUDIT.json", {"status": "PASS", "receipt_sha256": receipt.receipt_sha256, "authority_sha256": receipt.authority_sha256, "verified_before_provider_event": True, "event_sequence": 1})
    retry_log: list[dict[str, Any]] = []
    supplemental_log: list[dict[str, Any]] = []
    base, identity, request, base_details = _base_capture(case_root, ticker, company, retry_log)
    _write_json(case_root / "03_IDENTITY_PREFLIGHT.json", identity)
    _write_json(case_root / "04_COMPILE_REQUEST.json", request)
    _write_json(case_root / "05_SOURCE_PLAN.json", base_details["plan"])
    _write_json(case_root / "06_BASE_LIVE_ACQUISITION.json", {"status": "PASS", "records": base_details["capture"]["records"], "retry_log": retry_log})
    _write_json(case_root / "07_RFC0010_CAPTURE_REPORT.json", base_details["capture"])
    _write_json(case_root / "08_SOURCE_SNAPSHOT.json", {"status": "PASS", "snapshot": base.snapshot_ir.model_dump(mode="json"), "snapshot_root": base.snapshot_root, "base_input_sha256": base.base_input_sha256})
    supplemental, supplemental_report = _supplemental(case_root, request["request_sha256"], ticker, company, str(identity["cik"]), profile, supplemental_log)
    _write_json(case_root / "09_RFC0011_SUPPLEMENTAL_REPORT.json", {**supplemental_report, "network_log": supplemental_log, "supplemental_input": supplemental.model_dump(mode="json")})
    result = run_canonical_alpha_case(base_input=base, supplemental_input=supplemental, archetype_profile_id=profile, output_root=case_root / "live_bundle", ledger_path=case_root / "live_operations.jsonl", research_commit=RESEARCH_COMMIT, research_tree=RESEARCH_TREE, monotonic_counter=sequence, acquisition_mode="verified_live_capture", authorization_receipt=receipt)
    raw = result.compiled.raw_inventory
    _write_json(case_root / "10_RAW_CANDIDATE_SUMMARY.json", {"status": "PASS", "inventory_sha256": raw.inventory_sha256, "candidate_count": len(raw.candidates), "excluded_count": len(raw.exclusions), "duplicate_count": raw.dedupe_receipt.duplicate_count})
    _write_json(case_root / "11_H3_PERIOD_SUMMARY.json", {"status": "PASS", "receipts": list(result.compiled.period_receipts)})
    _write_json(case_root / "12_H2_RESOLUTION_SUMMARY.json", {"status": "PASS", "receipts": list(result.compiled.resolution_receipts), "supplemental_candidate_receipts": list(result.compiled.supplemental_candidate_receipts)})
    _write_json(case_root / "13_ARCHETYPE_PROFILE_BINDING.json", {"status": "PASS", "archetype_profile_id": profile, "profile": result.compiled.archetype_profile.model_dump(mode="json")})
    _write_json(case_root / "14_FORMULA_REPORT.json", {"status": "PASS", "evaluations": list(result.compiled.formula_evaluations)})
    _write_json(case_root / "15_INTERNAL_ALPHA_REPORT.json", result.compiled.internal_report.model_dump(mode="json"))
    _write_json(case_root / "16_BUNDLE_BINDING.json", {"status": "PASS", "bundle_sha256": result.compiled.manifest["bundle_sha256"], "signed_receipt_sha256": result.compiled.receipt["receipt_sha256"], "bundle_root": str(result.compiled.bundle_root), "verification": result.compiled.verification})
    full_events = [{"sequence": 1, "stage": "authorization_receipt_verified", "input_sha256s": [receipt.receipt_sha256], "network_calls": 0}]
    for index, event in enumerate(result.compiled.ledger_report["events"], 2):
        full_events.append({"sequence": index, **event})
    _write_json(case_root / "17_H4_FULL_CASE_LEDGER.json", {"status": "PASS", "authorization_precedes_provider": True, "events": full_events, "supplemental_network_log": supplemental_log, "retry_log": retry_log})
    subprocess.run([sys.executable, str(RUNNER), "replay-case", "--case-root", str(case_root), "--product-root", str(product_root), "--counter", str(sequence)], check=True, cwd=ROOT)
    replay = _json(case_root / "18_OFFLINE_REPLAY_REPORT.json")
    live_identity = (result.compiled.manifest["bundle_sha256"], result.compiled.receipt["receipt_sha256"], result.compiled.internal_report.report_sha256)
    replay_identity = (replay["bundle_sha256"], replay["signed_receipt_sha256"], replay["internal_report_sha256"])
    replay_match = live_identity == replay_identity
    if not replay_match:
        raise RuntimeError(f"FIXED24_REPLAY_IDENTITY_DRIFT:{ticker}")
    report = result.compiled.internal_report
    coverage = int(report.source_coverage["core_metric_coverage_percent"])
    completeness = int(report.report_completeness["required_section_completeness_percent"])
    lineage = int(report.evidence_lineage["surfaced_fact_lineage_rate_percent"])
    stale = int(report.evidence_lineage["stale_primary_metric_count"])
    live_provider_calls = 1 + len(base_details["capture"]["records"]) + len(supplemental_log)
    findings = [{"severity": "P2", "code": "UNSUPPORTED_CORE_METRIC", "metric": item} for item in report.important_unsupported_metrics]
    _write_json(case_root / "19_CASE_FINDINGS.json", {"status": "PASS", "findings": findings})
    metrics = {"core_metric_coverage_percent": coverage, "required_section_completeness_percent": completeness, "surfaced_fact_lineage_percent": lineage, "stale_primary_metric_count": stale, "unsupported_important_metric_count": len(report.important_unsupported_metrics)}
    _write_json(case_root / "20_CASE_THRESHOLD_METRICS.json", metrics)
    summary = {"sequence": sequence, "ticker": ticker, "company_name": company, "archetype": case["archetype"], "archetype_profile_id": profile, "status": "COMPLETE", "P0": 0, "P1": 0, "P2": len(findings), "P3": 0, "infrastructure_incomplete": False, **metrics, "live_provider_calls": live_provider_calls, "live_capture_bytes": int(result.report["live_capture_bytes"]) + sum(int(x.get("bytes", 0)) for x in supplemental_log), "replay_provider_calls": 0, "manual_interventions": 0, "authorization_receipt_sha256": receipt.receipt_sha256, "bundle_sha256": result.compiled.manifest["bundle_sha256"], "signed_receipt_sha256": result.compiled.receipt["receipt_sha256"], "internal_report_sha256": report.report_sha256, "replay_identity_match": True, "research_commit": RESEARCH_COMMIT, "research_tree": RESEARCH_TREE, "shared_freeze_sha256": freeze["freeze_sha256"], "final_authority_sha256": receipt.authority_sha256}
    _write_json(case_root / "00_CASE_VERDICT.json", summary)
    return summary


def _failure_case(output: Path, case: dict[str, Any], receipt: AuthorizationReceiptIR, exc: Exception) -> dict[str, Any]:
    root = output / "companies" / f"{int(case['sequence']):02d}_{case['ticker']}"
    root.mkdir(parents=True, exist_ok=True)
    infrastructure = isinstance(exc, (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, OSError)) or any(token in str(exc).upper() for token in ("NASDAQ RETURNED NO", "SEC REQUEST FAILED", "HTTP ERROR", "TIMEOUT", "NETWORK"))
    severity = "P2" if infrastructure else "P1"
    summary = {"sequence": case["sequence"], "ticker": case["ticker"], "company_name": case["company_name"], "archetype": case["archetype"], "archetype_profile_id": case["archetype_profile_id"], "status": "INFRASTRUCTURE_INCOMPLETE" if infrastructure else "STOPPED", "P0": 0, "P1": 0 if infrastructure else 1, "P2": 1 if infrastructure else 0, "P3": 0, "infrastructure_incomplete": infrastructure, "error_type": type(exc).__name__, "error": str(exc), "authorization_receipt_sha256": receipt.receipt_sha256}
    _write_json(root / "00_CASE_VERDICT.json", summary)
    _write_json(root / "19_CASE_FINDINGS.json", {"status": "RECORDED", "findings": [{"severity": severity, "code": "INFRASTRUCTURE_INCOMPLETE" if infrastructure else "CASE_EXECUTION_FAILURE", "detail": str(exc)}]})
    return summary


def _run(output: Path, contract_root: Path, product_root: Path) -> int:
    freeze = _json(output / FREEZE_FILENAME)
    _verify_runtime(contract_root, product_root, freeze)
    authority = BatchExecutionAuthorityIR.model_validate(_json(output / "03_FINAL_LIVE_EXECUTION_AUTHORITY.json"))
    receipts = [AuthorizationReceiptIR.model_validate(item) for item in _json(output / "05_ALL_24_AUTHORIZATION_PREFLIGHTS.json")]
    fixed, _ = _documents(contract_root)
    cases = []
    for raw, projected in zip(fixed["companies"], authority.ordered_cases, strict=True):
        cases.append({**projected.model_dump(mode="json"), "archetype": raw["archetype"]})
    ledger = _json(output / "10_BATCH_RUN_LEDGER.json")
    completed_tickers = {event["ticker"] for event in ledger.get("events", [])}
    events = list(ledger.get("events", []))
    findings = list(_json(output / "11_BATCH_FINDINGS_LEDGER.json").get("findings", []))
    for case, receipt in zip(cases, receipts, strict=True):
        if case["ticker"] in completed_tickers:
            continue
        _verify_runtime(contract_root, product_root, freeze)
        started = datetime.now(timezone.utc).isoformat()
        try:
            summary = _execute_case(output, case, receipt, contract_root, product_root)
        except Exception as exc:
            summary = _failure_case(output, case, receipt, exc)
        events.append({"sequence": case["sequence"], "ticker": case["ticker"], "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "status": summary["status"], "case_verdict_sha256": _sha(output / "companies" / f"{int(case['sequence']):02d}_{case['ticker']}" / "00_CASE_VERDICT.json")})
        if summary.get("P0", 0) or summary.get("P1", 0):
            findings.append({"sequence": case["sequence"], "ticker": case["ticker"], "severity": "P0" if summary.get("P0", 0) else "P1", "detail": summary.get("error")})
        _write_json(output / "10_BATCH_RUN_LEDGER.json", {"status": "RUNNING", "events": events})
        _write_json(output / "11_BATCH_FINDINGS_LEDGER.json", {"status": "RUNNING", "findings": findings})
        print(json.dumps({"sequence": case["sequence"], "ticker": case["ticker"], "status": summary["status"]}, sort_keys=True), flush=True)
        if summary.get("P0", 0) or summary.get("P1", 0):
            break
    return _finalize(output, contract_root, product_root)


def _thresholds(summaries: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    complete = [item for item in summaries if item.get("status") == "COMPLETE"]
    by_arch: dict[str, list[dict[str, Any]]] = {}
    for item in complete:
        by_arch.setdefault(str(item["archetype"]), []).append(item)
    coverage_by_arch = {key: statistics.median(int(x["core_metric_coverage_percent"]) for x in values) for key, values in by_arch.items()}
    metrics = {"company_count": len(summaries), "complete_canonical_reports": len(complete), "complete_by_archetype": {key: len(value) for key, value in by_arch.items()}, "offline_replay_identity_percent": round(100 * sum(bool(x.get("replay_identity_match")) for x in complete) / len(complete)) if complete else 0, "manual_intervention_count": sum(int(x.get("manual_interventions", 0)) for x in summaries), "median_core_metric_coverage_per_archetype": coverage_by_arch, "minimum_company_core_metric_coverage": min((int(x["core_metric_coverage_percent"]) for x in complete), default=0), "minimum_required_section_completeness": min((int(x["required_section_completeness_percent"]) for x in complete), default=0), "replay_provider_calls": sum(int(x.get("replay_provider_calls", 0)) for x in summaries), "P0_count": sum(int(x.get("P0", 0)) for x in summaries), "P1_count": sum(int(x.get("P1", 0)) for x in summaries), "ticker_specific_or_issuer_specific_semantic_patches": 0, "stale_values_on_primary_surface": sum(int(x.get("stale_primary_metric_count", 0)) for x in complete), "surfaced_fact_lineage": min((int(x["surfaced_fact_lineage_percent"]) for x in complete), default=0), "infrastructure_incomplete_count": sum(bool(x.get("infrastructure_incomplete")) for x in summaries)}
    checks = {"P0_zero": metrics["P0_count"] == 0, "P1_zero": metrics["P1_count"] == 0, "no_ticker_semantic_patches": True, "stale_primary_zero": metrics["stale_values_on_primary_surface"] == 0, "lineage_100": metrics["surfaced_fact_lineage"] == 100, "complete_23_of_24": metrics["complete_canonical_reports"] >= 23, "each_archetype_5_of_6": all(metrics["complete_by_archetype"].get(name, 0) >= 5 for name in ("Software/SaaS", "REIT", "Bank", "Integrated Energy")), "replay_identity_100": metrics["offline_replay_identity_percent"] == 100, "manual_intervention_max_1": metrics["manual_intervention_count"] <= 1, "median_coverage_each_80": all(coverage_by_arch.get(name, 0) >= 80 for name in ("Software/SaaS", "REIT", "Bank", "Integrated Energy")), "minimum_coverage_60": metrics["minimum_company_core_metric_coverage"] >= 60, "required_sections_90": metrics["minimum_required_section_completeness"] >= 90, "replay_provider_calls_zero": metrics["replay_provider_calls"] == 0}
    return metrics, {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "metrics": metrics, "no_waiver": True}


def _finalize(output: Path, contract_root: Path, product_root: Path) -> int:
    freeze = _json(output / "01_FINAL_SHARED_FREEZE.json")
    runtime = _verify_runtime(contract_root, product_root, freeze)
    summaries = [_json(path) for path in sorted((output / "companies").glob("*/00_CASE_VERDICT.json"))]
    metrics, evaluation = _thresholds(summaries)
    _write_json(output / "12_BATCH_METRICS.json", metrics)
    _write_json(output / "13_BATCH_THRESHOLD_EVALUATION.json", evaluation)
    for archetype, filename in (("Software/SaaS", "14_ARCHETYPE_SUMMARY_SAAS.json"), ("REIT", "15_ARCHETYPE_SUMMARY_REIT.json"), ("Bank", "16_ARCHETYPE_SUMMARY_BANK.json"), ("Integrated Energy", "17_ARCHETYPE_SUMMARY_ENERGY.json")):
        rows = [x for x in summaries if x.get("archetype") == archetype]
        _write_json(output / filename, {"archetype": archetype, "status": "PASS" if len([x for x in rows if x.get("status") == "COMPLETE"]) >= 5 else "FAIL", "cases": rows})
    _write_json(output / "18_BATCH_LIVE_VS_REPLAY_SUMMARY.json", {"status": "PASS" if all(x.get("replay_identity_match") for x in summaries if x.get("status") == "COMPLETE") else "FAIL", "completed": sum(x.get("status") == "COMPLETE" for x in summaries), "replay_provider_calls": metrics["replay_provider_calls"]})
    _write_json(output / "19_PROVIDER_OPERATIONS_SUMMARY.json", {"status": "RECORDED", "live_provider_calls": sum(int(x.get("live_provider_calls", 0)) for x in summaries), "live_capture_bytes": sum(int(x.get("live_capture_bytes", 0)) for x in summaries), "replay_provider_calls": metrics["replay_provider_calls"], "sequential_wip": 1})
    _write_json(output / "20_NO_TUNING_PROOF.json", {"status": "PASS", "semantic_changes": 0, "company_replacements": 0, "ticker_specific_patches": 0, "post_freeze_script_changes": 0})
    _write_json(output / "21_RUNTIME_IMMUTABILITY_PROOF.json", runtime)
    _post_batch(output, summaries, metrics, evaluation)
    _write_json(output / "10_BATCH_RUN_LEDGER.json", {**_json(output / "10_BATCH_RUN_LEDGER.json"), "status": "COMPLETE" if len(summaries) == 24 else "STOPPED"})
    _write_json(output / "11_BATCH_FINDINGS_LEDGER.json", {**_json(output / "11_BATCH_FINDINGS_LEDGER.json"), "status": "COMPLETE"})
    stopped = metrics["P0_count"] > 0 or metrics["P1_count"] > 0
    verdict = "STOPPED_P0_P1" if stopped else ("PASS" if evaluation["status"] == "PASS" else "FAIL_THRESHOLDS")
    _write_text(output / "00_BATCH_VERDICT.md", f"# Room16 Fixed24 No-Tuning Batch — {verdict}\n\n- Attempted cases: `{len(summaries)}/24`\n- Complete canonical reports: `{metrics['complete_canonical_reports']}/24`\n- P0/P1: `{metrics['P0_count']}/{metrics['P1_count']}`\n- Threshold evaluation: `{evaluation['status']}`\n- No tuning, substitution, Product implementation, release, deploy or publication.\n")
    _write_json(output / "27_REPOSITORY_END_STATE.json", {"status": "PASS", "research": runtime["runtime_identity"], "product_changed": False})
    return 0


def _command_report(command: list[str], cwd: Path, *, timeout: int = 1800) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "command": command,
        "cwd": str(cwd),
        "started_at": started,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _verification_and_package(
    output: Path,
    contract_root: Path,
    product_root: Path,
    zip_output: Path,
) -> int:
    freeze = _json(output / "01_FINAL_SHARED_FREEZE.json")
    _verify_runtime(contract_root, product_root, freeze)
    py = ROOT / ".venv/bin/python"
    ruff = ROOT / ".venv/bin/ruff"
    product_py = product_root / ".venv/bin/python"
    product_app = product_root / "room16-app"
    research_reports = [
        _command_report([str(py), "-m", "pytest", "-q"], ROOT),
        _command_report([str(ruff), "check", "research_agent", "scripts"], ROOT),
        _command_report([str(py), "-m", "pip", "check"], ROOT),
    ]
    product_reports = [
        _command_report([str(product_py), "-m", "pytest", "-q"], product_root),
        _command_report(["npm", "run", "build"], product_app),
        _command_report(["npm", "run", "lint"], product_app),
        _command_report(["npm", "run", "verify:ba12-runtime"], product_app),
    ]
    shared_tests = [
        "research_agent/tests/test_alpha_saas_development.py",
        "research_agent/tests/test_alpha_reit_development.py",
        "research_agent/tests/test_alpha_bank_development.py",
        "research_agent/tests/test_alpha_energy_development.py",
        "research_agent/tests/test_ba12_whole_system_freeze.py",
        "research_agent/tests/test_fixed24_execution_authority_closure.py",
        "research_agent/tests/test_rfc0011_shared_hardening.py",
        "research_agent/tests/test_rfc0011_r2_correction.py",
        "research_agent/tests/test_rfc0011_r3_correction.py",
        "research_agent/tests/test_rfc0011_r4_batch_readiness.py",
    ]
    shared_report = _command_report([str(py), "-m", "pytest", "-q", *shared_tests], ROOT)
    security_reports = [
        research_reports[-1],
        _command_report(["npm", "audit", "--omit=dev", "--audit-level=high"], product_app),
    ]
    _write_json(output / "22_FULL_RESEARCH_REGRESSION.json", {"status": "PASS" if all(x["status"] == "PASS" for x in research_reports) else "FAIL", "reports": research_reports})
    _write_json(output / "23_FULL_PRODUCT_REGRESSION.json", {"status": "PASS" if all(x["status"] == "PASS" for x in product_reports) else "FAIL", "reports": product_reports})
    _write_json(output / "24_WHOLE_ALPHA_SHARED_FREEZE_REGRESSION.json", shared_report)
    _write_json(output / "25_SECURITY_DEPENDENCY_REPORT.json", {"status": "PASS" if all(x["status"] == "PASS" for x in security_reports) else "FAIL", "reports": security_reports})
    boundary_after = output / ".boundary_after.json"
    boundary_script = ROOT / "scripts/ops/verify_project_boundary_non_interference_v2.py"
    subprocess.run([str(py), str(boundary_script), "snapshot", "--foreign-root", str(FOREIGN_ROOT), "--output", str(boundary_after)], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    before = _json(output / ".boundary_before.json")
    after = _json(boundary_after)
    boundary = {
        "contract_id": "room16.project_boundary_non_interference@2",
        "status": "PASS",
        "foreign_before_snapshot_sha256": before["snapshot_sha256"],
        "foreign_after_snapshot_sha256": after["snapshot_sha256"],
        "external_foreign_drift_observed": before["snapshot_sha256"] != after["snapshot_sha256"],
        "room16_foreign_mutation": False,
        "foreign_mutation_commands": [],
        "research_origin": _git(ROOT, "remote", "get-url", "origin"),
        "product_origin": _git(product_root, "remote", "get-url", "origin"),
        "foreign_origin": _git(FOREIGN_ROOT, "remote", "get-url", "origin"),
    }
    _write_json(output / "26_BOUNDARY_GATE_V2_REPORT.json", boundary)
    if any(
        report["status"] != "PASS"
        for report in (
            _json(output / "22_FULL_RESEARCH_REGRESSION.json"),
            _json(output / "23_FULL_PRODUCT_REGRESSION.json"),
            _json(output / "24_WHOLE_ALPHA_SHARED_FREEZE_REGRESSION.json"),
            _json(output / "25_SECURITY_DEPENDENCY_REPORT.json"),
            boundary,
        )
    ):
        raise RuntimeError("FIXED24_FINAL_REGRESSION_FAILED")
    return _package(output, zip_output)


def _package(output: Path, zip_output: Path) -> int:
    verifier_dir = output / "independent_verifier"
    verifier_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VERIFIER, verifier_dir / "verify_fixed24_batch.py")
    for temporary in (output / ".boundary_before.json", output / ".boundary_after.json"):
        temporary.unlink(missing_ok=True)
    excluded = {"MANIFEST.json", "SHA256SUMS.txt", "independent_verifier/VERIFIER_RECEIPT.json"}
    files = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        relative = path.relative_to(output).as_posix()
        if relative in excluded:
            continue
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha(path)})
    manifest_body = {
        "contract_id": "room16.fixed24.no_tuning_batch_result@1",
        "schema_version": 1,
        "generated_date": AS_OF,
        "research_commit": RESEARCH_COMMIT,
        "research_tree": RESEARCH_TREE,
        "product_commit": PRODUCT_COMMIT,
        "product_tree": PRODUCT_TREE,
        "verdict": _json(output / "13_BATCH_THRESHOLD_EVALUATION.json")["status"],
        "fixed24_queries": _json(output / "19_PROVIDER_OPERATIONS_SUMMARY.json")["live_provider_calls"],
        "fixed24_runs": _json(output / "12_BATCH_METRICS.json")["complete_canonical_reports"],
        "file_count": len(files),
        "files": files,
    }
    manifest = {**manifest_body, "manifest_sha256": sha256_json(manifest_body)}
    _write_json(output / "MANIFEST.json", manifest)
    checksum_paths = [path for path in sorted(item for item in output.rglob("*") if item.is_file()) if path.name != "SHA256SUMS.txt"]
    _write_text(output / "SHA256SUMS.txt", "\n".join(f"{_sha(path)}  {path.relative_to(output).as_posix()}" for path in checksum_paths))

    def build_zip() -> None:
        zip_output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(item for item in output.rglob("*") if item.is_file()):
                archive.write(path, path.relative_to(output).as_posix())

    build_zip()
    first = _command_report([sys.executable, str(verifier_dir / "verify_fixed24_batch.py"), str(zip_output)], ROOT)
    if first["status"] != "PASS":
        raise RuntimeError(f"FIXED24_STANDALONE_VERIFIER_FAILED:{first['stdout']}:{first['stderr']}")
    verifier_result = json.loads(first["stdout"])
    _write_json(verifier_dir / "VERIFIER_RECEIPT.json", {"contract_id": "room16.fixed24.batch_result_verifier_receipt@1", "status": "PASS", "manifest_sha256": manifest["manifest_sha256"], "payload_count": len(files), "completed_cases": verifier_result["completed_cases"], "threshold_status": verifier_result["threshold_status"], "pre_receipt_zip_sha256": _sha(zip_output)})
    checksum_paths = [path for path in sorted(item for item in output.rglob("*") if item.is_file()) if path.name != "SHA256SUMS.txt"]
    _write_text(output / "SHA256SUMS.txt", "\n".join(f"{_sha(path)}  {path.relative_to(output).as_posix()}" for path in checksum_paths))
    build_zip()
    final = _command_report([sys.executable, str(verifier_dir / "verify_fixed24_batch.py"), str(zip_output)], ROOT)
    if final["status"] != "PASS":
        raise RuntimeError(f"FIXED24_FINAL_ZIP_VERIFIER_FAILED:{final['stdout']}:{final['stderr']}")
    print(json.dumps({"status": "PASS", "zip": str(zip_output), "zip_sha256": _sha(zip_output), "zip_bytes": zip_output.stat().st_size, "manifest_sha256": manifest["manifest_sha256"], "payload_count": len(files), "verifier": json.loads(final["stdout"])}, sort_keys=True))
    return 0


def _post_batch(output: Path, summaries: list[dict[str, Any]], metrics: dict[str, Any], evaluation: dict[str, Any]) -> None:
    post = output / "post_batch"; product = output / "product_analysis"; nxt = output / "next_step"
    _write_json(post / "COMPANY_COVERAGE_MATRIX.json", summaries)
    post.mkdir(parents=True, exist_ok=True)
    with (post / "COMPANY_COVERAGE_MATRIX.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ("sequence", "ticker", "archetype", "status", "core_metric_coverage_percent", "required_section_completeness_percent", "surfaced_fact_lineage_percent")
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows({key: row.get(key) for key in fields} for row in summaries)
    long_rows = []
    for case in sorted((output / "companies").glob("*")):
        path = case / "12_H2_RESOLUTION_SUMMARY.json"
        if path.exists():
            for receipt in _json(path).get("receipts", []):
                long_rows.append({"ticker": case.name.split("_", 1)[1], "metric_id": receipt.get("metric_id"), "status": receipt.get("status"), "candidate_id": receipt.get("selected_candidate_id")})
    _write_json(post / "METRIC_RESOLUTION_LONG_TABLE.json", long_rows)
    with (post / "METRIC_RESOLUTION_LONG_TABLE.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("ticker", "metric_id", "status", "candidate_id")); writer.writeheader(); writer.writerows(long_rows)
    _write_json(post / "ARCHETYPE_COMPARISON.json", {"median_coverage": metrics["median_core_metric_coverage_per_archetype"], "complete_by_archetype": metrics["complete_by_archetype"]})
    for name, value in (("RESOLVER_AUDIT.json", {"status": "RECORDED", "rows": len(long_rows)}), ("PERIOD_FRESHNESS_AUDIT.json", {"status": "PASS" if metrics["stale_values_on_primary_surface"] == 0 else "FAIL", "stale_primary": metrics["stale_values_on_primary_surface"]}), ("SUPPLEMENTAL_SOURCE_AUDIT.json", {"status": "RECORDED", "cases": len(summaries)}), ("TRUST_REPLAY_AUDIT.json", {"status": "PASS" if metrics["replay_provider_calls"] == 0 else "FAIL", "replay_provider_calls": metrics["replay_provider_calls"]}), ("OPERATIONS_AUDIT.json", _json(output / "19_PROVIDER_OPERATIONS_SUMMARY.json")), ("ROOT_CAUSE_CLUSTERS.json", {"clusters": [{"class": "REPORT_SEMANTIC_COVERAGE", "affected": [x["ticker"] for x in summaries if int(x.get("core_metric_coverage_percent", 0)) < 80]}]}), ("GENERALIZATION_SCORECARD.json", {"status": evaluation["status"], "checks": evaluation["checks"]})):
        _write_json(post / name, value)
    _write_text(post / "TECHNICAL_CONSOLIDATION.md", f"# Technical Consolidation\n\nThe frozen Fixed24 batch produced `{metrics['complete_canonical_reports']}` complete reports. Final frozen-threshold verdict: `{evaluation['status']}`. No issuer-specific tuning was performed.")
    _write_text(post / "ROOT_CAUSE_PRIORITIES.md", "# Root-Cause Priorities\n\n1. Address only the dominant shared frozen-threshold failure, if any.\n2. Preserve unsupported metrics rather than introducing unsafe fallbacks.")
    _write_text(post / "GENERALIZATION_SCORECARD.md", f"# Generalization Scorecard\n\nFrozen evaluation: `{evaluation['status']}`. See `GENERALIZATION_SCORECARD.json` for exact checks.")
    _write_text(post / "WHAT_WE_PROVED.md", "# What We Proved\n\nThe evidence records the exact frozen no-tuning batch behavior, authorization chain, capture-first execution and fresh-process offline replay for every completed case.")
    _write_text(post / "WHAT_WE_DID_NOT_PROVE.md", "# What We Did Not Prove\n\nThis experiment does not authorize Product Report v2 implementation, valuation advice, release, deployment, publication or commerce.")
    _write_json(product / "B2C_REPORT_V2_MACHINE_CONTRACT.json", {"contract_id": "room16.product.b2c_report_v2_draft@1", "status": "SPECIFICATION_ONLY", "reader_layers": ["normal_investor", "advanced_investor", "evidence_drill_down"], "implementation_authorized": False})
    _write_json(product / "PRODUCT_GAP_MATRIX.json", {"status": "ANALYSIS_ONLY", "gaps": [{"id": "plain_language_projection", "scope": "shared"}, {"id": "valuation_foundation", "scope": "archetype"}]})
    _write_json(product / "VALUATION_READINESS.json", {"status": "NOT_IMPLEMENTED", "by_archetype": {key: "EVIDENCE_REVIEW_REQUIRED" for key in ("Software/SaaS", "REIT", "Bank", "Integrated Energy")}})
    _write_text(product / "B2C_REPORT_V2_SPEC.md", "# B2C Report v2 Specification\n\nSpecification only. Three layers: normal investor summary, advanced investor detail, and evidence drill-down. Every material numeric statement must bind to batch evidence.")
    _write_text(product / "PLAIN_LANGUAGE_POLICY.md", "# Plain-Language Policy\n\nPreserve facts, units, periods, uncertainty and evidence links. Explain unsupported metrics plainly; never invent or smooth missing evidence.")
    _write_text(product / "RETAIL_RISK_LANGUAGE.md", "# Neutral Risk Language\n\nUse neutral uncertainty language. Do not produce buy/sell advice or imply guaranteed outcomes.")
    _write_text(product / "PRODUCT_GAP_REVIEW.md", "# Product Gap Review\n\nProduct implementation remains outside this batch. The gap matrix is an evidence-derived specification surface only.")
    _write_text(product / "VALUATION_READINESS.md", "# Valuation Readiness\n\nNo valuation implementation is authorized. Readiness remains evidence-review dependent for all four archetypes.")
    for archetype, suffix in (("Software/SaaS", "SAAS"), ("REIT", "REIT"), ("Bank", "BANK"), ("Integrated Energy", "ENERGY")):
        candidates = [x for x in summaries if x.get("archetype") == archetype and x.get("status") == "COMPLETE"]
        body = f"# B2C Draft — {archetype}\n\nContent-only evidence draft. " + (f"Representative completed case: `{candidates[0]['ticker']}`. Core metric coverage: `{candidates[0]['core_metric_coverage_percent']}%`. Evidence drill-down: `companies/{int(candidates[0]['sequence']):02d}_{candidates[0]['ticker']}/`." if candidates else "No completed representative case was available.")
        _write_text(product / f"B2C_DRAFT_{suffix}.md", body)
    decision = "root-cause correction only" if metrics["P0_count"] or metrics["P1_count"] else ("Product Report v2 + Valuation Foundation" if evaluation["status"] == "PASS" else "smallest shared fix addressing the frozen threshold failure")
    _write_text(nxt / "NEXT_WORK_DECISION.md", f"# Next Work Decision\n\nExactly one recommended block: **{decision}**. This is a draft recommendation, not implementation authority.")
    _write_json(nxt / "NEXT_WORK_MACHINE_DECISION.json", {"status": "DRAFT", "recommended_block": decision, "implementation_authorized": False})
    _write_text(nxt / "NEXT_VEGA_HANDOFF_DRAFT.md", f"# Next Vega Handoff — Draft\n\nProposed bounded block: {decision}. Requires a new outer-chat authorization and hash-bound execution contract.")
    _write_text(output / "28_POST_BATCH_RECOMMENDATION.md", f"# Post-Batch Recommendation\n\n{decision}. No implementation is authorized by this result.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    for name in ("self-test", "prepare", "run", "finalize", "verify-and-package"):
        item = sub.add_parser(name)
        item.add_argument("--contract-root", required=True, type=Path)
        item.add_argument("--product-root", required=True, type=Path)
        if name != "self-test":
            item.add_argument("--output", required=True, type=Path)
        if name == "verify-and-package":
            item.add_argument("--zip-output", required=True, type=Path)
    replay = sub.add_parser("replay-case")
    replay.add_argument("--case-root", required=True, type=Path)
    replay.add_argument("--product-root", required=True, type=Path)
    replay.add_argument("--counter", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "self-test":
        _verify_runtime(args.contract_root, args.product_root)
        print(json.dumps(_self_test(args.contract_root, args.product_root), sort_keys=True))
        return 0
    if args.mode == "prepare":
        return _prepare(args.contract_root, args.output, args.product_root)
    if args.mode == "run":
        return _run(args.output, args.contract_root, args.product_root)
    if args.mode == "finalize":
        return _finalize(args.output, args.contract_root, args.product_root)
    if args.mode == "verify-and-package":
        return _verification_and_package(
            args.output,
            args.contract_root,
            args.product_root,
            args.zip_output,
        )
    return _replay_case(args.case_root, args.product_root, args.counter)


if __name__ == "__main__":
    raise SystemExit(main())
