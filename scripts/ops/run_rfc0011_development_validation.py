#!/usr/bin/env python3
"""Run bounded RFC-0011 live validation for the four Development issuers."""

from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from research_agent.alpha_shared.contracts import DiscoveryRequestIR, SupplementalSourcePolicyIR
from research_agent.alpha_shared.document_normalizer import discover_observations, normalize_document
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.operations_ledger import OperationsLedger
from research_agent.alpha_shared.source_authority import NetworkResponse, SupplementalSourceAuthority
from research_agent.compiler_foundation.canonical import sha256_json

DEVELOPMENT = {
    "CRM": {"cik": "1108524", "name": "Salesforce, Inc.", "metrics": ("crpo", "guidance")},
    "JPM": {"cik": "19617", "name": "JPMorgan Chase & Co.", "metrics": ("efficiency_ratio", "net_interest_margin", "rotce")},
    "PLD": {"cik": "1045609", "name": "Prologis, Inc.", "metrics": ("adjusted_ffo", "occupancy", "same_store_noi")},
    "XOM": {"cik": "34088", "name": "Exxon Mobil Corporation", "metrics": ("production_volume", "segment_operating_results")},
}
USER_AGENT = "BCRAdmin Room16 RFC0011 contact@bcradmin.com"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _fetch(locator: str) -> NetworkResponse:
    request = urllib.request.Request(
        locator,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip", "Accept": "application/json,text/html,text/plain"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            payload = gzip.decompress(payload)
        media_type = response.headers.get_content_type()
        final_locator = response.geturl()
        status = str(response.status)
    time.sleep(0.12)
    return NetworkResponse(
        payload=payload,
        final_locator=final_locator,
        media_type=media_type,
        fetched_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        status=status,
    )


def _policy(ticker: str, values: dict[str, object], as_of_date: str) -> SupplementalSourcePolicyIR:
    return SupplementalSourcePolicyIR.create(
        base_request_sha256=sha256_json({"ticker": ticker, "as_of_date": as_of_date, "frozen_base": True}),
        ticker=ticker,
        canonical_company_name=str(values["name"]),
        issuer_cik=str(values["cik"]),
        as_of_date=as_of_date,
        allowed_source_family_ids=("sec_filed_exhibit", "sec_primary_document", "structured_regulatory_dataset"),
        allowed_domains=("data.sec.gov", "www.sec.gov"),
        allowed_media_types=("application/json", "application/xhtml+xml", "text/html", "text/plain"),
        allowed_sec_forms=("10-K", "10-Q", "8-K"),
        max_discovery_requests=4,
        max_candidates=250,
        max_selected_documents=3,
        max_bytes_per_document=20_000_000,
        discovery_lookback_days=550,
        paid_provider_ids_allowed=(),
        network_mode="live_acquisition",
    )


def _event(ledger: OperationsLedger, run_id: str, stage: str, *, network: int, capture_bytes: int, outputs: tuple[str, ...], status: str = "PASS", diagnostics: tuple[str, ...] = ()) -> None:
    ledger.append(
        run_id=run_id,
        stage=stage,
        attempt=1,
        started_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        ended_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        duration_ms=0,
        status=status,
        network_call_count=network,
        capture_bytes=capture_bytes,
        input_sha256s=(),
        output_sha256s=outputs,
        diagnostic_codes=diagnostics,
    )


def run_issuer(root: Path, ticker: str, values: dict[str, object], as_of_date: str) -> dict[str, object]:
    issuer_root = root / ticker
    policy = _policy(ticker, values, as_of_date)
    authority = SupplementalSourceAuthority(policy, issuer_root / "capture_store")
    ledger = OperationsLedger(issuer_root / "operations.jsonl")
    run_id = f"rfc0011.dev.{ticker.lower()}.{as_of_date}"
    submissions_locator = f"https://data.sec.gov/submissions/CIK{str(values['cik']).zfill(10)}.json"
    submissions_request = DiscoveryRequestIR.create(
        request_id=f"discovery.sec.submissions.{ticker.lower()}",
        policy_sha256=policy.policy_sha256,
        source_family_id="sec_primary_document",
        locator=submissions_locator,
    )
    submissions_receipt = authority.capture_discovery(submissions_request, _fetch)
    primary_candidates = authority.derive_sec_submission_candidates(submissions_receipt)
    eligible_primary = [item for item in primary_candidates if item.form in {"10-Q", "10-K"}]
    if not eligible_primary:
        raise RuntimeError(f"{ticker}: no eligible SEC primary document")
    primary = sorted(eligible_primary, key=lambda item: (item.filing_date, item.accession_number), reverse=True)[0]
    exhibit_parents = [item for item in primary_candidates if item.form == "8-K"]
    exhibit_parent = sorted(exhibit_parents, key=lambda item: (item.filing_date, item.accession_number), reverse=True)[0]
    accession_path = exhibit_parent.accession_number.replace("-", "")
    cik_path = str(int(str(values["cik"])))
    index_locator = f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}/index.json"
    index_request = DiscoveryRequestIR.create(
        request_id=f"discovery.sec.index.{ticker.lower()}",
        policy_sha256=policy.policy_sha256,
        source_family_id="sec_filed_exhibit",
        locator=index_locator,
    )
    index_receipt = authority.capture_discovery(index_request, _fetch)
    exhibits = authority.derive_filing_index_candidates(
        index_receipt,
        issuer_cik=str(values["cik"]),
        accession_number=exhibit_parent.accession_number,
        filing_date=exhibit_parent.filing_date,
        report_date=exhibit_parent.report_date,
        form=exhibit_parent.form,
        primary_document=exhibit_parent.document_name,
    )
    combined = tuple(primary_candidates) + tuple(exhibits)
    candidate_set = authority.candidate_set((submissions_receipt, index_receipt), combined)
    selected = (primary,) + tuple(exhibits[:1])
    evidence = authority.capture_selected(candidate_set, selected, _fetch)
    _event(
        ledger,
        run_id,
        "live_capture",
        network=2 + len(selected),
        capture_bytes=submissions_receipt.payload_bytes + index_receipt.payload_bytes + sum(item.payload_bytes for item in evidence.capture_receipts),
        outputs=(candidate_set.set_sha256, evidence.evidence_set_sha256),
    )
    candidate_by_id = {item.candidate_id: item for item in candidate_set.candidates}
    profiles = label_profiles()
    requested_profiles = {metric: profiles[metric] for metric in values["metrics"]}
    observations = []
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
        observations.extend(item.model_dump(mode="json") for item in discover_observations(document, requested_profiles))
    if not observations:
        raise RuntimeError(f"{ticker}: no relevant deterministic observation")
    _event(ledger, run_id, "normalize_observe", network=0, capture_bytes=0, outputs=tuple(item["observation_sha256"] for item in observations))
    replay = authority.replay(candidate_set, evidence.capture_receipts)
    if replay.evidence_set_sha256 != evidence.evidence_set_sha256:
        raise RuntimeError(f"{ticker}: replay evidence hash mismatch")
    _event(ledger, run_id, "offline_replay", network=0, capture_bytes=0, outputs=(replay.evidence_set_sha256,))
    _event(ledger, run_id, "complete", network=0, capture_bytes=0, outputs=(ledger.verify()[-1].event_sha256,))
    result = {
        "status": "PASS",
        "ticker": ticker,
        "company": values["name"],
        "cik": values["cik"],
        "network_query_count": 2 + len(selected),
        "queried_tickers": [ticker],
        "discovery_captured_before_parse": True,
        "documents_captured_before_normalize": True,
        "source_families_captured": sorted({candidate_by_id[item.candidate_id].source_family_id for item in evidence.capture_receipts}),
        "candidate_count": len(candidate_set.candidates),
        "selected_document_count": len(selected),
        "observation_count": len(observations),
        "observation_metric_classes": sorted({item["reported_basis_text_or_null"] for item in observations}),
        "candidate_set_sha256": candidate_set.set_sha256,
        "evidence_set_sha256": evidence.evidence_set_sha256,
        "offline_replay_evidence_set_sha256": replay.evidence_set_sha256,
        "offline_replay_network_call_count": 0,
        "policy": policy.model_dump(mode="json"),
        "discovery_receipts": [submissions_receipt.model_dump(mode="json"), index_receipt.model_dump(mode="json")],
        "candidate_set": candidate_set.model_dump(mode="json"),
        "evidence_set": evidence.model_dump(mode="json"),
        "normalized_documents": normalized,
        "observations": observations,
        "operations_aggregate": ledger.aggregate(),
    }
    _write_json(issuer_root / "validation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of-date", default="2026-08-27")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")
    results = [run_issuer(args.output, ticker, values, args.as_of_date) for ticker, values in sorted(DEVELOPMENT.items())]
    report = {
        "contract_id": "room16.rfc0011.development_live_validation",
        "contract_version": 1,
        "status": "PASS",
        "allowed_live_tickers": sorted(DEVELOPMENT),
        "queried_tickers": sorted(item["ticker"] for item in results),
        "forbidden_holdout_query_count": 0,
        "fixed24_query_count": 0,
        "results": results,
    }
    _write_json(args.output / "DEVELOPMENT_LIVE_VALIDATION.json", report)
    print(json.dumps({"status": "PASS", "issuers": len(results), "observations": sum(item["observation_count"] for item in results)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
