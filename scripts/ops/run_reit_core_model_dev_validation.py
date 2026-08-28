#!/usr/bin/env python3
"""Run the frozen Room16 REIT Development6 core-slot-v2 validation wave."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from research_agent.alpha_shared.archetype_profiles import archetype_profile_registry
from research_agent.alpha_shared.contracts import (
    DiscoveryRequestIR,
    DocumentObservationIR,
    SharedBaseInputIR,
    SupplementalCompileInputIR,
    SupplementalSourcePolicyIR,
)
from research_agent.alpha_shared.core_slots import (
    REIT_OPERATING_PERFORMANCE_GRADES,
    core_slot_registry,
)
from research_agent.alpha_shared.document_normalizer import (
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.execution_authority import (
    AuthorizationReceiptIR,
    BatchExecutionAuthorityIR,
    BatchExecutionCaseIR,
    RuntimeIdentityIR,
    authorize_case_before_network,
)
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.runner import (
    replay_canonical_alpha_case,
    run_canonical_alpha_case,
)
from research_agent.alpha_shared.source_authority import (
    NetworkResponse,
    SupplementalSourceAuthority,
    is_earnings_filed_exhibit_name,
    is_sec_index_page,
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
AS_OF = "2026-08-28"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_TREE = "a382d9c096825910b5e0e8865414ea232b95bd40"
PRIOR_RESULT_SHA = "24533635de4c2aa2addaa4d649715d849187a643b5e2e4aff4924dbf4d3f1d4d"
PRIOR_MANIFEST_SHA = "7a94e34f3deb3d2d01e0a31ee38f9f078596b3c25cb0fe91de200a0b8dc50171"
DEV6_SET_SHA = "21a585b88bbcfb4adcb02e82f8d00f32bf59fb73d79f67e145e645f5e0b23dae"
HOLDOUT12_SHA = "4fa4c0171f098d59b206cd270e60fb497800aa152d63cca66290aee35e6a5b7f"
RESEARCH_ORIGIN = "https://github.com/BCRAdmin/deterministic-research-core.git"
PRODUCT_ORIGIN = "https://github.com/BCRAdmin/company-dossier-lab.git"
FOREIGN_ROOT = Path(
    "/Users/BjornRosinger/Documents/DreamFactory/Utility-Websites/materialbedarf-rechner.de"
)
USER_AGENT = os.environ.get(
    "ROOM16_SEC_USER_AGENT", "BCRAdmin Room16 REIT validation contact@bcradmin.com"
)
DEV6 = (
    (1, "AMT", "American Tower Corporation"),
    (2, "EQIX", "Equinix, Inc."),
    (3, "PSA", "Public Storage"),
    (4, "CUBE", "CubeSmart"),
    (5, "EGP", "EastGroup Properties, Inc."),
    (6, "REXR", "Rexford Industrial Realty, Inc."),
)
SUPPLEMENTAL_METRICS = (
    "reported_ffo",
    "reported_core_ffo",
    "reported_affo",
    "occupancy",
    "same_store_noi",
)
FROZEN_SOURCES = (
    "research_agent/alpha_shared/core_slots.py",
    "research_agent/alpha_shared/archetype_profiles.py",
    "research_agent/alpha_shared/internal_report.py",
    "research_agent/alpha_shared/metric_semantics.py",
    "research_agent/alpha_shared/supplemental_semantics.py",
    "research_agent/alpha_shared/source_authority.py",
    "research_agent/alpha_shared/observation_registry.py",
    "research_agent/tests/test_reit_core_slot_v2.py",
    "research_agent/tests/test_fixed24_shared_coverage_correction.py",
    "scripts/ops/run_reit_core_model_dev_validation.py",
    "scripts/ops/finalize_reit_core_model_dev_validation.py",
    "scripts/ops/verify_reit_core_model_dev_validation.py",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _runtime(product_root: Path) -> RuntimeIdentityIR:
    return RuntimeIdentityIR(
        research_commit=_git(ROOT, "rev-parse", "HEAD"),
        research_tree=_git(ROOT, "rev-parse", "HEAD^{tree}"),
        product_commit=_git(product_root, "rev-parse", "HEAD"),
        product_tree=_git(product_root, "rev-parse", "HEAD^{tree}"),
        as_of_date=AS_OF,
    )


def _tracked_clean(repo: Path) -> bool:
    return not _git(repo, "status", "--porcelain", "--untracked-files=no")


def _foreign_snapshot() -> dict[str, object]:
    if not (FOREIGN_ROOT / ".git").exists():
        return {"path": str(FOREIGN_ROOT), "present": False, "mode": "READ_ONLY"}
    return {
        "path": str(FOREIGN_ROOT),
        "present": True,
        "mode": "READ_ONLY",
        "origin": _git(FOREIGN_ROOT, "remote", "get-url", "origin"),
        "head": _git(FOREIGN_ROOT, "rev-parse", "HEAD"),
        "tree": _git(FOREIGN_ROOT, "rev-parse", "HEAD^{tree}"),
        "status": _git(FOREIGN_ROOT, "status", "--short", "--branch"),
    }


def _validate_contract_documents(contract_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _read_json(contract_root / "06_REIT_DEVELOPMENT6_PLAN.json")
    holdout = _read_json(contract_root / "07_UNTOUCHED_HOLDOUT12_BINDING.json")
    projected = tuple(
        (int(item["sequence"]), str(item["ticker"]), str(item["company_name"]))
        for item in plan["companies"]
    )
    if projected != DEV6 or plan.get("set_sha256") != DEV6_SET_SHA:
        raise RuntimeError("REIT_DEV6_CONTRACT_DRIFT")
    if holdout.get("frozen_list_sha256") != HOLDOUT12_SHA:
        raise RuntimeError("HOLDOUT12_CONTRACT_DRIFT")
    if {item["ticker"] for item in holdout["companies"]} & {item[1] for item in DEV6}:
        raise RuntimeError("DEV6_HOLDOUT_OVERLAP")
    return plan, holdout


def _authority(runtime: RuntimeIdentityIR) -> BatchExecutionAuthorityIR:
    cases = tuple(
        BatchExecutionCaseIR(
            sequence=sequence,
            ticker=ticker,
            company_name=company,
            archetype_profile_id="reit",
        )
        for sequence, ticker, company in DEV6
    )
    return BatchExecutionAuthorityIR.create(
        authority_kind="DEVELOPMENT_VALIDATION",
        as_of_date=AS_OF,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=None,
        fixed_company_list_sha256=None,
        threshold_sha256=None,
        ordered_cases=cases,
        network_live_authorized=True,
    )


def _profile_slots() -> dict[str, tuple[str, ...]]:
    registry = archetype_profile_registry()
    return {
        str(item["archetype_profile_id"]): tuple(item["required_core_metrics"])
        for item in registry["profiles"]
    }


def _prestart(contract_root: Path, product_root: Path, output: Path) -> int:
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("REIT_DEV6_OUTPUT_NOT_EMPTY")
    plan, holdout = _validate_contract_documents(contract_root)
    runtime = _runtime(product_root)
    if _git(ROOT, "remote", "get-url", "origin") != RESEARCH_ORIGIN:
        raise RuntimeError("RESEARCH_ORIGIN_MISMATCH")
    if _git(product_root, "remote", "get-url", "origin") != PRODUCT_ORIGIN:
        raise RuntimeError("PRODUCT_ORIGIN_MISMATCH")
    if (runtime.product_commit, runtime.product_tree) != (PRODUCT_COMMIT, PRODUCT_TREE):
        raise RuntimeError("PRODUCT_IDENTITY_DRIFT")
    if not _tracked_clean(ROOT) or not _tracked_clean(product_root):
        raise RuntimeError("TRACKED_WORKTREE_NOT_CLEAN")
    if _git(ROOT, "rev-parse", "@{u}") != runtime.research_commit:
        raise RuntimeError("RESEARCH_REMOTE_DRIFT")
    authority = _authority(runtime)
    receipts = tuple(
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
        )
        for case in authority.ordered_cases
    )
    hashes = {relative: _sha(ROOT / relative) for relative in FROZEN_SOURCES}
    slot_registry = core_slot_registry(_profile_slots())
    freeze_body = {
        "contract_id": "room16.reit.dev6_prestart_freeze",
        "contract_version": 1,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "as_of_date": AS_OF,
        "runtime_identity": runtime.model_dump(mode="json"),
        "research_origin": RESEARCH_ORIGIN,
        "research_remote_head": _git(ROOT, "rev-parse", "@{u}"),
        "product_origin": PRODUCT_ORIGIN,
        "product_changed": False,
        "dev6_set_sha256": DEV6_SET_SHA,
        "holdout12_list_sha256": HOLDOUT12_SHA,
        "dev6_plan_sha256": _sha(contract_root / "06_REIT_DEVELOPMENT6_PLAN.json"),
        "holdout12_binding_sha256": _sha(
            contract_root / "07_UNTOUCHED_HOLDOUT12_BINDING.json"
        ),
        "core_slot_registry_sha256": slot_registry["registry_sha256"],
        "frozen_source_hashes": hashes,
        "authority": authority.model_dump(mode="json"),
        "authorization_receipts": [item.model_dump(mode="json") for item in receipts],
        "authorized_tickers_in_order": [item[1] for item in DEV6],
        "fixed24_non_reit_live_queries": 0,
        "holdout12_queries": 0,
        "holdout12_runs": 0,
        "network_queries_before_freeze": 0,
        "foreign_repository_before": _foreign_snapshot(),
        "no_tuning_required": True,
        "semantic_changes_after_freeze_authorized": False,
    }
    freeze = {**freeze_body, "freeze_sha256": sha256_json(freeze_body)}
    output.mkdir(parents=True)
    _write_json(output / "07_REIT_DEV6_PRESTART_FREEZE.json", freeze)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/ops/verify_project_boundary_non_interference_v2.py"),
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
    _write_json(output / ".dev6_plan.json", plan)
    _write_json(output / ".holdout12_binding.json", holdout)
    _write_json(output / ".core_slot_registry.json", slot_registry)
    print(json.dumps({"status": "PASS", "freeze_sha256": freeze["freeze_sha256"], "network_queries": 0}, sort_keys=True))
    return 0


def _verify_freeze(product_root: Path, output: Path) -> tuple[dict[str, Any], RuntimeIdentityIR]:
    freeze = _read_json(output / "07_REIT_DEV6_PRESTART_FREEZE.json")
    body = {key: value for key, value in freeze.items() if key != "freeze_sha256"}
    if sha256_json(body) != freeze["freeze_sha256"]:
        raise RuntimeError("REIT_DEV6_FREEZE_SELFHASH_DRIFT")
    runtime = _runtime(product_root)
    if runtime.model_dump(mode="json") != freeze["runtime_identity"]:
        raise RuntimeError("REIT_DEV6_RUNTIME_DRIFT")
    if not _tracked_clean(ROOT) or not _tracked_clean(product_root):
        raise RuntimeError("REIT_DEV6_TRACKED_WORKTREE_DRIFT")
    for relative, expected in freeze["frozen_source_hashes"].items():
        if _sha(ROOT / relative) != expected:
            raise RuntimeError(f"REIT_DEV6_SOURCE_DRIFT:{relative}")
    if _foreign_snapshot() != freeze["foreign_repository_before"]:
        raise RuntimeError("REIT_DEV6_FOREIGN_BOUNDARY_DRIFT")
    return freeze, runtime


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
                transient = isinstance(
                    exc,
                    (
                        urllib.error.HTTPError,
                        urllib.error.URLError,
                        TimeoutError,
                        ConnectionError,
                        OSError,
                        RuntimeError,
                    ),
                )
                status = "RETRY" if transient and retry < 3 else "FAIL"
                self.log.append(
                    {"method": name, "retry": retry, "status": status, "error": type(exc).__name__}
                )
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
                request = urllib.request.Request(
                    locator,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept-Encoding": "gzip",
                        "Accept": "application/json,text/html,text/plain",
                    },
                )
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = response.read()
                    if response.headers.get("Content-Encoding") == "gzip":
                        payload = gzip.decompress(payload)
                    result = NetworkResponse(
                        payload=payload,
                        final_locator=response.geturl(),
                        media_type=response.headers.get_content_type(),
                        fetched_at_utc=datetime.now(timezone.utc)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        status=str(response.status),
                    )
                self.log.append(
                    {"locator": locator, "retry": retry, "status": "PASS", "bytes": len(payload)}
                )
                time.sleep(0.5)
                return result
            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                TimeoutError,
                ConnectionError,
                OSError,
            ) as exc:
                last = exc
                self.log.append(
                    {
                        "locator": locator,
                        "retry": retry,
                        "status": "RETRY" if retry < 3 else "FAIL",
                        "error": type(exc).__name__,
                    }
                )
                if retry >= 3:
                    raise
                delay = (1, 2, 4)[retry]
                if isinstance(exc, urllib.error.HTTPError):
                    header = exc.headers.get("Retry-After")
                    if header and header.isdigit():
                        delay = int(header)
                time.sleep(delay)
        raise RuntimeError("unreachable retry state") from last


def _resolve_identity(
    ticker: str, company_name: str, sec: RetryAdapter
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = sec.get_company_tickers()
    matches = [
        row
        for row in payload.values()
        if isinstance(row, dict) and str(row.get("ticker") or "").upper() == ticker
    ]
    if len(matches) != 1:
        raise RuntimeError(f"REIT_DEV6_IDENTITY_NOT_UNIQUE:{ticker}:{len(matches)}")
    match = matches[0]
    resolution = {
        "status": "supported",
        "runtimeReady": True,
        "inputKind": "ticker",
        "input": ticker,
        "ticker": ticker,
        "companyName": company_name,
        "exchange": "US Listed",
        "exchangeCode": "US",
        "jurisdiction": "US",
        "isin": None,
        "source": "SEC company_tickers.json",
    }
    identity = {
        "status": "PASS",
        "provider_query_count": 1,
        "ticker": ticker,
        "company_name": company_name,
        "sec_title": match.get("title"),
        "cik": str(match["cik_str"]),
        "matched_record": match,
        "resolution": resolution,
    }
    return resolution, identity


def _base_capture(
    case_root: Path, ticker: str, company: str, retry_log: list[dict[str, Any]]
) -> tuple[SharedBaseInputIR, dict[str, Any], dict[str, Any], dict[str, Any]]:
    sec = RetryAdapter(
        SecClient(
            SecClientConfig(
                user_agent=USER_AGENT,
                request_delay_seconds=0.5,
                timeout_seconds=30,
                max_retries=1,
                use_cache=False,
            )
        ),
        retry_log,
    )
    resolution, identity = _resolve_identity(ticker, company, sec)
    request = build_compile_request(
        resolution,
        as_of_date=AS_OF,
        allowed_provider_ids=("nasdaq", "sec"),
        available_configuration_ids=("ROOM16_SEC_USER_AGENT",),
        network_mode="live_acquisition",
    )
    plan = plan_source_acquisition(request, price_provider_id="nasdaq")
    executor = LiveCaptureExecutor(case_root / "captures/rfc0010")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    cutoff = datetime.combine(
        date.fromisoformat(AS_OF), datetime.max.time(), tzinfo=timezone.utc
    ).replace(microsecond=0)
    authority_time = min(now, cutoff).isoformat().replace("+00:00", "Z")
    start = (date.fromisoformat(AS_OF) - timedelta(days=400)).isoformat()
    nasdaq = RetryAdapter(NasdaqPriceProvider(), retry_log)
    cik = str(identity["cik"])
    adapters = {
        "sec": ExistingAdapterHarness(
            provider_id="sec",
            adapter=sec,
            method_name="get_companyfacts",
            source_id=f"SEC_COMPANYFACTS_CIK{cik.zfill(10)}",
            source_type="sec_filing",
            original_locator=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json",
            final_locator=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json",
            raw_status="200",
            media_type="application/json",
            fetched_at_utc=authority_time,
            available_at_utc=authority_time,
            args=(cik,),
        ),
        "nasdaq": ExistingAdapterHarness(
            provider_id="nasdaq",
            adapter=nasdaq,
            method_name="get_history",
            source_id=f"NASDAQ_OHLCV_{ticker}",
            source_type="exchange_ohlcv",
            original_locator=f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/historical",
            final_locator=f"https://api.nasdaq.com/api/quote/{ticker}/historical",
            raw_status="200",
            media_type="application/json",
            fetched_at_utc=authority_time,
            available_at_utc=authority_time,
            args=(ticker, start, AS_OF),
        ),
    }
    records = tuple(
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id=item.acquisition_id,
            attempt_id=f"reit-dev6.{ticker.lower()}.{item.provider_id}.1",
            adapter=adapters[item.provider_id],
        )
        for item in plan.acquisitions
    )
    snapshot_root = case_root / "captures/ba3_snapshot"
    bridge = bridge_capture_set_to_ba3(
        request=request,
        plan=plan,
        records=records,
        capture_store_root=executor.capture_store.root,
        snapshot_root=snapshot_root,
        staged_at_utc=authority_time,
    )
    verification = verify_live_bridge(
        records=records,
        result=bridge,
        capture_store_root=executor.capture_store.root,
    )
    base = SharedBaseInputIR.from_snapshot(snapshot=bridge.snapshot, snapshot_root=snapshot_root)
    details = {
        "plan": plan.model_dump(mode="json"),
        "capture": {
            "status": "PASS",
            "records": [
                {
                    "receipt": item.receipt.model_dump(mode="json"),
                    "artifact": item.artifact.model_dump(mode="json"),
                }
                for item in records
            ],
            "capture_set": bridge.capture_set.model_dump(mode="json"),
            "closure": bridge.closure.model_dump(mode="json"),
            "bridge_verification": verification,
            "snapshot": bridge.snapshot.model_dump(mode="json"),
            "snapshot_root": str(snapshot_root),
        },
    }
    return base, identity, request.model_dump(mode="json"), details


def _supplemental(
    case_root: Path,
    request_sha: str,
    ticker: str,
    company: str,
    cik: str,
    fetch_log: list[dict[str, Any]],
) -> tuple[SupplementalCompileInputIR, dict[str, Any]]:
    policy = SupplementalSourcePolicyIR.create(
        base_request_sha256=request_sha,
        ticker=ticker,
        canonical_company_name=company,
        issuer_cik=cik,
        as_of_date=AS_OF,
        allowed_source_family_ids=(
            "sec_filed_exhibit",
            "sec_primary_document",
            "structured_regulatory_dataset",
        ),
        allowed_domains=("data.sec.gov", "www.sec.gov"),
        allowed_media_types=(
            "application/json",
            "application/xhtml+xml",
            "text/html",
            "text/plain",
        ),
        allowed_sec_forms=("10-K", "10-Q", "8-K"),
        max_discovery_requests=4,
        max_candidates=250,
        max_selected_documents=3,
        max_bytes_per_document=20_000_000,
        discovery_lookback_days=550,
        paid_provider_ids_allowed=(),
        network_mode="live_acquisition",
    )
    authority = SupplementalSourceAuthority(policy, case_root / "captures/rfc0011")
    fetcher = SupplementalFetcher(fetch_log)
    submissions_request = DiscoveryRequestIR.create(
        request_id=f"reit.dev6.discovery.submissions.{ticker.lower()}",
        policy_sha256=policy.policy_sha256,
        source_family_id="sec_primary_document",
        locator=f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json",
    )
    submissions = authority.capture_discovery(submissions_request, fetcher)
    primary_candidates = authority.derive_sec_submission_candidates(submissions)
    discovery = [submissions]
    exhibits: tuple[Any, ...] = ()
    parents = [item for item in primary_candidates if item.form == "8-K"]
    if parents:
        parent = max(
            parents,
            key=lambda item: (item.filing_date, item.accession_number, item.document_name),
        )
        index_request = DiscoveryRequestIR.create(
            request_id=f"reit.dev6.discovery.index.{ticker.lower()}",
            policy_sha256=policy.policy_sha256,
            source_family_id="sec_filed_exhibit",
            locator=(
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{parent.accession_number.replace('-', '')}/index.json"
            ),
        )
        index_receipt = authority.capture_discovery(index_request, fetcher)
        discovery.append(index_receipt)
        exhibits = authority.derive_filing_index_candidates(
            index_receipt,
            issuer_cik=cik,
            accession_number=parent.accession_number,
            filing_date=parent.filing_date,
            report_date=parent.report_date,
            form=parent.form,
            primary_document=parent.document_name,
        )
    candidate_set = authority.candidate_set(
        tuple(discovery), tuple(primary_candidates) + tuple(exhibits)
    )
    selected = authority.select(candidate_set)
    if any(is_sec_index_page(item.document_name) for item in selected):
        raise RuntimeError(f"REIT_DEV6_INDEX_PAGE_SELECTED:{ticker}")
    evidence = authority.capture_selected(candidate_set, selected, fetcher)
    candidate_by_id = {item.candidate_id: item for item in candidate_set.candidates}
    requested = {metric: label_profiles()[metric] for metric in SUPPLEMENTAL_METRICS}
    observations: list[DocumentObservationIR] = []
    normalized = []
    for receipt in evidence.capture_receipts:
        candidate = candidate_by_id[receipt.candidate_id]
        _, payload = authority.store.load_verified(receipt.payload_sha256)
        document = normalize_document(
            payload,
            document_id=candidate.candidate_id,
            accession_number=candidate.accession_number,
            report_date=candidate.report_date,
            filing_date=candidate.filing_date,
            document_name=candidate.document_name,
            media_type=receipt.media_type,
        )
        normalized.append(document.model_dump(mode="json"))
        observations.extend(discover_observations(document, requested))
    replay = authority.replay(candidate_set, evidence.capture_receipts)
    if replay.evidence_set_sha256 != evidence.evidence_set_sha256:
        raise RuntimeError(f"REIT_DEV6_SUPPLEMENTAL_REPLAY_DRIFT:{ticker}")
    supplemental = SupplementalCompileInputIR.create(
        supplemental_policy_sha256=policy.policy_sha256,
        discovery_set_sha256=candidate_set.set_sha256,
        supplemental_evidence_set_sha256=evidence.evidence_set_sha256,
        observations=tuple(observations),
    )
    return supplemental, {
        "status": "PASS",
        "policy": policy.model_dump(mode="json"),
        "discovery_receipts": [item.model_dump(mode="json") for item in discovery],
        "candidate_set": candidate_set.model_dump(mode="json"),
        "selected_documents": [item.model_dump(mode="json") for item in selected],
        "selected_earnings_exhibit": any(
            item.source_family_id == "sec_filed_exhibit"
            and is_earnings_filed_exhibit_name(item.document_name)
            for item in selected
        ),
        "index_or_header_selected": False,
        "evidence_set": evidence.model_dump(mode="json"),
        "normalized_documents": normalized,
        "observations": [item.model_dump(mode="json") for item in observations],
        "supplemental_input": supplemental.model_dump(mode="json"),
        "offline_replay_network_calls": 0,
    }


def _replay_case(case_root: Path, research_commit: str, research_tree: str, counter: int) -> int:
    base_report = _read_json(case_root / "08_SOURCE_SNAPSHOT.json")
    base = SharedBaseInputIR.from_snapshot(
        snapshot=SourceSnapshotIR.model_validate(base_report["snapshot"]),
        snapshot_root=Path(base_report["snapshot_root"]),
    )
    supplemental = SupplementalCompileInputIR.model_validate(
        _read_json(case_root / "09_RFC0011_SUPPLEMENTAL_REPORT.json")["supplemental_input"]
    )
    result = replay_canonical_alpha_case(
        base_input=base,
        supplemental_input=supplemental,
        archetype_profile_id="reit",
        output_root=case_root / "replay_bundle",
        ledger_path=case_root / "replay_operations.jsonl",
        research_commit=research_commit,
        research_tree=research_tree,
        monotonic_counter=counter,
    )
    _write_json(
        case_root / "18_OFFLINE_REPLAY_REPORT.json",
        {
            "status": "PASS",
            "network_provider_calls": 0,
            "bundle_sha256": result.compiled.manifest["bundle_sha256"],
            "signed_receipt_sha256": result.compiled.receipt["receipt_sha256"],
            "internal_report_sha256": result.compiled.internal_report.report_sha256,
            "runner_report": result.report,
        },
    )
    return 0


def _execute_case(
    output: Path,
    sequence: int,
    ticker: str,
    company: str,
    receipt: AuthorizationReceiptIR,
    runtime: RuntimeIdentityIR,
) -> dict[str, Any]:
    case_root = output / "companies_dev6" / f"{sequence:02d}_{ticker}"
    if case_root.exists():
        raise RuntimeError(f"REIT_DEV6_CASE_OUTPUT_EXISTS:{ticker}")
    case_root.mkdir(parents=True)
    _write_json(case_root / "01_AUTHORIZATION_RECEIPT.json", receipt.model_dump(mode="json"))
    retry_log: list[dict[str, Any]] = []
    supplemental_log: list[dict[str, Any]] = []
    base, identity, request, details = _base_capture(case_root, ticker, company, retry_log)
    _write_json(case_root / "03_IDENTITY_PREFLIGHT.json", identity)
    _write_json(case_root / "04_COMPILE_REQUEST.json", request)
    _write_json(case_root / "05_SOURCE_PLAN.json", details["plan"])
    _write_json(
        case_root / "06_BASE_LIVE_ACQUISITION.json",
        {"status": "PASS", "records": details["capture"]["records"], "retry_log": retry_log},
    )
    _write_json(case_root / "07_RFC0010_CAPTURE_REPORT.json", details["capture"])
    _write_json(
        case_root / "08_SOURCE_SNAPSHOT.json",
        {
            "status": "PASS",
            "snapshot": base.snapshot_ir.model_dump(mode="json"),
            "snapshot_root": base.snapshot_root,
            "base_input_sha256": base.base_input_sha256,
        },
    )
    supplemental, supplemental_report = _supplemental(
        case_root,
        request["request_sha256"],
        ticker,
        company,
        str(identity["cik"]),
        supplemental_log,
    )
    _write_json(
        case_root / "09_RFC0011_SUPPLEMENTAL_REPORT.json",
        {**supplemental_report, "network_log": supplemental_log},
    )
    result = run_canonical_alpha_case(
        base_input=base,
        supplemental_input=supplemental,
        archetype_profile_id="reit",
        output_root=case_root / "live_bundle",
        ledger_path=case_root / "live_operations.jsonl",
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        monotonic_counter=sequence,
        acquisition_mode="verified_live_capture",
        authorization_receipt=receipt,
    )
    report = result.compiled.internal_report
    _write_json(case_root / "15_INTERNAL_ALPHA_REPORT.json", report.model_dump(mode="json"))
    _write_json(
        case_root / "16_BUNDLE_BINDING.json",
        {
            "status": "PASS",
            "bundle_sha256": result.compiled.manifest["bundle_sha256"],
            "signed_receipt_sha256": result.compiled.receipt["receipt_sha256"],
            "verification": result.compiled.verification,
        },
    )
    _write_json(
        case_root / "17_LIVE_LEDGER.json",
        {
            "status": "PASS",
            "authorization_precedes_provider": True,
            "events": result.compiled.ledger_report["events"],
            "base_retry_log": retry_log,
            "supplemental_network_log": supplemental_log,
        },
    )
    subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "replay-case",
            "--case-root",
            str(case_root),
            "--research-commit",
            runtime.research_commit,
            "--research-tree",
            runtime.research_tree,
            "--counter",
            str(sequence),
        ],
        check=True,
        cwd=ROOT,
    )
    replay = _read_json(case_root / "18_OFFLINE_REPLAY_REPORT.json")
    live_identity = (
        result.compiled.manifest["bundle_sha256"],
        result.compiled.receipt["receipt_sha256"],
        report.report_sha256,
    )
    replay_identity = (
        replay["bundle_sha256"],
        replay["signed_receipt_sha256"],
        replay["internal_report_sha256"],
    )
    if live_identity != replay_identity:
        raise RuntimeError(f"REIT_DEV6_REPLAY_IDENTITY_DRIFT:{ticker}")
    slots = list(report.core_slot_resolutions)
    operating = next(item for item in slots if item["slot_id"] == "reit_operating_performance_measure")
    ffo_candidates = [
        item
        for item in supplemental_report["observations"]
        if item.get("label_id") in REIT_OPERATING_PERFORMANCE_GRADES
    ]
    summary = {
        "sequence": sequence,
        "ticker": ticker,
        "company_name": company,
        "archetype": "REIT",
        "archetype_profile_id": "reit",
        "status": "COMPLETE",
        "P0": 0,
        "P1": 0,
        "P2": len(report.important_unsupported_metrics),
        "infrastructure_incomplete": False,
        "core_slot_coverage_percent": report.source_coverage["core_slot_coverage_percent"],
        "required_core_slot_count": report.source_coverage["required_core_slot_count"],
        "covered_core_slot_count": report.source_coverage["covered_core_slot_count"],
        "required_section_completeness_percent": report.report_completeness[
            "required_section_completeness_percent"
        ],
        "surfaced_fact_lineage_percent": report.evidence_lineage[
            "surfaced_fact_lineage_rate_percent"
        ],
        "stale_primary_metric_count": report.evidence_lineage["stale_primary_metric_count"],
        "core_slot_resolutions": slots,
        "operating_measure_slot": operating,
        "ffo_family_candidate_count": len(ffo_candidates),
        "ffo_family_candidates": ffo_candidates,
        "selected_documents": supplemental_report["selected_documents"],
        "selected_earnings_exhibit": supplemental_report["selected_earnings_exhibit"],
        "index_or_header_selected": False,
        "live_provider_calls": 1 + len(details["capture"]["records"]) + len(supplemental_log),
        "replay_provider_calls": 0,
        "replay_identity_match": True,
        "bundle_sha256": live_identity[0],
        "signed_receipt_sha256": live_identity[1],
        "internal_report_sha256": live_identity[2],
        "authorization_receipt_sha256": receipt.receipt_sha256,
    }
    _write_json(case_root / "00_CASE_VERDICT.json", summary)
    return summary


def _infrastructure_failure(exc: Exception) -> bool:
    text = str(exc).upper()
    return isinstance(
        exc,
        (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, OSError),
    ) or any(
        token in text
        for token in ("NASDAQ RETURNED NO", "SEC REQUEST FAILED", "HTTP ERROR", "TIMEOUT", "NETWORK")
    )


def _run(product_root: Path, output: Path) -> int:
    freeze, runtime = _verify_freeze(product_root, output)
    authority = BatchExecutionAuthorityIR.model_validate(freeze["authority"])
    receipts = {
        item.ticker: item
        for item in (
            AuthorizationReceiptIR.model_validate(raw)
            for raw in freeze["authorization_receipts"]
        )
    }
    summaries = []
    for sequence, ticker, company in DEV6:
        _verify_freeze(product_root, output)
        try:
            summary = _execute_case(
                output, sequence, ticker, company, receipts[ticker], runtime
            )
        except Exception as exc:
            infrastructure = _infrastructure_failure(exc)
            summary = {
                "sequence": sequence,
                "ticker": ticker,
                "company_name": company,
                "archetype": "REIT",
                "status": "INFRASTRUCTURE_INCOMPLETE" if infrastructure else "STOPPED_P1",
                "P0": 0,
                "P1": 0 if infrastructure else 1,
                "P2": 1 if infrastructure else 0,
                "infrastructure_incomplete": infrastructure,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "replay_provider_calls": 0,
            }
            case_root = output / "companies_dev6" / f"{sequence:02d}_{ticker}"
            case_root.mkdir(parents=True, exist_ok=True)
            _write_json(case_root / "00_CASE_VERDICT.json", summary)
            summaries.append(summary)
            if not infrastructure:
                break
            continue
        summaries.append(summary)
    _verify_freeze(product_root, output)
    ledger = {
        "contract_id": "room16.reit.dev6_run_ledger",
        "contract_version": 1,
        "status": "STOPPED_P0_P1"
        if any(item.get("P0") or item.get("P1") for item in summaries)
        else "COMPLETE",
        "freeze_sha256": freeze["freeze_sha256"],
        "authority_sha256": authority.authority_sha256,
        "attempted_tickers": [item["ticker"] for item in summaries],
        "authorized_tickers": [item[1] for item in DEV6],
        "cases": summaries,
        "no_tuning": True,
        "tracked_changes_between_cases": 0,
        "fixed24_non_reit_live_queries": 0,
        "holdout12_queries": 0,
        "holdout12_runs": 0,
    }
    _write_json(output / "08_REIT_DEV6_RUN_LEDGER.json", ledger)
    print(json.dumps({"status": ledger["status"], "attempted": len(summaries)}, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    for name in ("prestart", "run"):
        item = sub.add_parser(name)
        item.add_argument("--product-root", type=Path, required=True)
        item.add_argument("--output", type=Path, required=True)
        if name == "prestart":
            item.add_argument("--contract-root", type=Path, required=True)
    replay = sub.add_parser("replay-case")
    replay.add_argument("--case-root", type=Path, required=True)
    replay.add_argument("--research-commit", required=True)
    replay.add_argument("--research-tree", required=True)
    replay.add_argument("--counter", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "prestart":
        return _prestart(args.contract_root, args.product_root, args.output)
    if args.mode == "run":
        return _run(args.product_root, args.output)
    return _replay_case(
        args.case_root, args.research_commit, args.research_tree, args.counter
    )


if __name__ == "__main__":
    raise SystemExit(main())
