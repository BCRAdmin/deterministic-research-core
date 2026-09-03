"""Additive, profile-scoped source extension authority.

This module deliberately sits beside the frozen BA3/RFC acquisition model.
It never mutates that historical contract and requires raw capture before any
discovery or semantic parsing.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from research_agent.profile_authority.integrity import SHA256_RE, canonical_sha256, with_self_hash

SEC_HOSTS = ("data.sec.gov", "www.sec.gov")


def build_source_extension_contract(
    *,
    family: str,
    version: int,
    discovery_parser_sha256: str,
    maximum_discovered_documents: int,
) -> dict[str, Any]:
    """Build the immutable descriptor for one profile source extension."""
    if not SHA256_RE.fullmatch(discovery_parser_sha256):
        raise ValueError("SOURCE_EXTENSION_PARSER_HASH_INVALID")
    if maximum_discovered_documents < 1 or maximum_discovered_documents > 8:
        raise ValueError("SOURCE_EXTENSION_DOCUMENT_BOUND_INVALID")
    body = {
        "contract_id": "room16.sector_source_extension_contract@1",
        "contract_version": 1,
        "profile_family": family,
        "profile_version": version,
        "permitted_providers": ["sec"],
        "permitted_domains": list(SEC_HOSTS),
        "discovery_source_types": ["SEC_SUBMISSIONS_JSON", "SEC_FILING_DIRECTORY_INDEX_JSON"],
        "discovery_parser_sha256": discovery_parser_sha256,
        "discovered_source_selection_rules": {
            "financial_forms": ["10-Q", "10-K"],
            "event_forms": ["8-K"],
            "qualifying_items": ["2.02", "7.01"],
            "qualifying_exhibit_filename_tokens": [
                "ex99",
                "exhibit99",
                "earnings",
                "supplement",
                "presentation",
            ],
            "deterministic_order": "filing_date_desc,accession_asc,document_name_asc",
        },
        "maximum_discovered_documents": maximum_discovered_documents,
        "target_forms_items_exhibits": [
            "10-Q",
            "10-K",
            "8-K:2.02",
            "8-K:7.01",
            "EX-99.1",
            "EX-99.2",
        ],
        "as_of_behavior": "FILING_DATE_AT_OR_BEFORE_AS_OF",
        "capture_before_parse_required": True,
        "content_sha256_required": True,
        "accession_and_document_identity_required": True,
        "ticker_specific_urls_or_rules": False,
        "live_response_semantic_parse_allowed": False,
        "discovered_source_set_receipt_required_before_document_fetch": True,
        "historical_base_acquisition_contract_modified": False,
    }
    return with_self_hash(body, "source_extension_sha256")


def validate_sec_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in SEC_HOSTS:
        raise ValueError("SOURCE_EXTENSION_UNAPPROVED_DOMAIN")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("SOURCE_EXTENSION_URL_IDENTITY_INVALID")


def captured_artifact(path: Path, *, url: str, media_type: str) -> dict[str, Any]:
    """Describe bytes only after they exist in the capture store."""
    validate_sec_url(url)
    if not path.is_file():
        raise ValueError("SOURCE_EXTENSION_CAPTURE_REQUIRED_BEFORE_PARSE")
    payload = path.read_bytes()
    return {
        "url": url,
        "media_type": media_type,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "capture_path": path.as_posix(),
        "captured_before_parse": True,
    }


def seal_discovered_source_set(
    *,
    ticker: str,
    cik: str,
    submissions_sha256: str,
    filing_index_artifacts: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    maximum_documents: int,
) -> dict[str, Any]:
    if not SHA256_RE.fullmatch(submissions_sha256):
        raise ValueError("DISCOVERY_SUBMISSIONS_HASH_INVALID")
    if len(documents) > maximum_documents:
        raise ValueError("DISCOVERY_DOCUMENT_BOUND_EXCEEDED")
    normalized = []
    seen: set[tuple[str, str]] = set()
    for row in documents:
        url = str(row.get("url", ""))
        validate_sec_url(url)
        accession = str(row.get("accession", ""))
        name = str(row.get("document_name", ""))
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            raise ValueError("DISCOVERY_ACCESSION_INVALID")
        if not name or "/" in name or "\\" in name or name in {".", ".."}:
            raise ValueError("DISCOVERY_DOCUMENT_IDENTITY_INVALID")
        identity = (accession, name)
        if identity in seen:
            raise ValueError("DISCOVERY_DOCUMENT_DUPLICATE")
        seen.add(identity)
        normalized.append(dict(row))
    normalized.sort(
        key=lambda row: (
            str(row.get("filing_date", "")),
            str(row.get("accession", "")),
            str(row.get("document_name", "")),
        ),
        reverse=True,
    )
    body = {
        "contract_id": "room16.discovered_source_set_receipt@1",
        "ticker": ticker.upper(),
        "cik": str(int(cik)),
        "submissions_sha256": submissions_sha256,
        "filing_index_artifacts": [dict(row) for row in filing_index_artifacts],
        "documents": normalized,
        "document_count": len(normalized),
        "maximum_documents": maximum_documents,
        "document_bytes_fetched_at_seal": 0,
        "result_fields_used_for_discovery": [],
        "ticker_specific_rules": False,
    }
    return with_self_hash(body, "discovered_source_set_sha256")


def verify_self_hash(value: Mapping[str, Any], field: str) -> str:
    supplied = str(value.get(field, ""))
    if not SHA256_RE.fullmatch(supplied):
        raise ValueError(f"SELF_HASH_INVALID:{field}")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != supplied:
        raise ValueError(f"SELF_HASH_MISMATCH:{field}")
    return supplied


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
