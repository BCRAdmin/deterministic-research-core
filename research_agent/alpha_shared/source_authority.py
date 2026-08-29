"""Capture-first RFC-0011 discovery, selection, capture, and replay."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from research_agent.ba12_live_source.capture_store import ContentAddressedCaptureStore

from .contracts import (
    CandidateSelectionContextIR,
    DiscoveryCaptureReceiptIR,
    DiscoveryRequestIR,
    DiscoveredSourceCandidateIR,
    DiscoveredSourceSetIR,
    SecFilingIntentIR,
    SecFilingIntentSetIR,
    SupplementalCaptureReceiptIR,
    SupplementalEvidenceSetIR,
    SupplementalSourceError,
    SupplementalSourcePolicyIR,
)


@dataclass(frozen=True)
class NetworkResponse:
    payload: bytes
    final_locator: str
    media_type: str
    fetched_at_utc: str
    status: str = "200"


NetworkFetcher = Callable[[str], NetworkResponse]

_INDEX_PAGE = re.compile(r"(?:^|-)index(?:-headers)?\.html?$", re.IGNORECASE)
_STRICT_EXHIBIT = re.compile(
    r"(?:^|[-_.])(?:ex|exhibit)[-_.]?99(?:[-_.]?\d+)?(?:[-_.]|$)", re.IGNORECASE
)
_EARNINGS_SIGNAL = re.compile(
    r"(?:^|[-_.])(?:earnings?|financial[-_]?results?|press[-_]?release|results?)(?:[-_.]|$)",
    re.IGNORECASE,
)
_NON_EARNINGS_SIGNAL = re.compile(
    r"(?:^|[-_.])(?:acquisition|disposition|dividend|governance|merger|offering|"
    r"presentation|proxy|restructuring)(?:[-_.]|$)",
    re.IGNORECASE,
)
_SEC_ITEM_CODE = re.compile(r"^[0-9]+\.[0-9]{2}$")


def is_sec_index_page(document_name: str) -> bool:
    return bool(_INDEX_PAGE.search(document_name.rsplit("/", 1)[-1]))


def is_strict_filed_exhibit_name(document_name: str) -> bool:
    """Use strict exhibit/earnings signals; arbitrary ``ex`` substrings never qualify."""

    name = document_name.rsplit("/", 1)[-1]
    if is_sec_index_page(name):
        return False
    stem = name.rsplit(".", 1)[0]
    return bool(_STRICT_EXHIBIT.search(stem) or _EARNINGS_SIGNAL.search(stem))


def is_earnings_filed_exhibit_name(document_name: str) -> bool:
    """Identify a generic earnings/results exhibit without issuer rules."""

    name = document_name.rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0]
    return is_strict_filed_exhibit_name(name) and not _NON_EARNINGS_SIGNAL.search(stem)


def _allowed_locator(locator: str, policy: SupplementalSourcePolicyIR) -> None:
    parsed = urlparse(locator)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in policy.allowed_domains:
        raise SupplementalSourceError("RFC0011_DOMAIN_BLOCKED", locator)
    if parsed.username or parsed.password or parsed.fragment:
        raise SupplementalSourceError("RFC0011_LOCATOR_UNSAFE", locator)


def _media_type(value: str) -> str:
    return value.split(";", 1)[0].strip().lower()


class SupplementalSourceAuthority:
    """Execute a policy already hash-bound before the first network call."""

    def __init__(self, policy: SupplementalSourcePolicyIR, root: Path) -> None:
        self.policy = SupplementalSourcePolicyIR.model_validate(policy.model_dump(mode="json"))
        self.store = ContentAddressedCaptureStore(root)
        self._discovery_count = 0

    def capture_discovery(
        self, request: DiscoveryRequestIR, fetcher: NetworkFetcher
    ) -> DiscoveryCaptureReceiptIR:
        if self.policy.network_mode != "live_acquisition":
            raise SupplementalSourceError("RFC0011_REPLAY_NETWORK_BLOCKED", request.locator)
        if request.policy_sha256 != self.policy.policy_sha256:
            raise SupplementalSourceError("RFC0011_POLICY_BINDING_MISMATCH", request.request_id)
        if request.source_family_id not in self.policy.allowed_source_family_ids:
            raise SupplementalSourceError("RFC0011_SOURCE_FAMILY_BLOCKED", request.source_family_id)
        if self._discovery_count >= self.policy.max_discovery_requests:
            raise SupplementalSourceError("RFC0011_DISCOVERY_LIMIT", request.request_id)
        _allowed_locator(request.locator, self.policy)
        self._discovery_count += 1
        response = fetcher(request.locator)
        _allowed_locator(response.final_locator, self.policy)
        media_type = _media_type(response.media_type)
        if media_type not in self.policy.allowed_media_types:
            raise SupplementalSourceError("RFC0011_MEDIA_TYPE_BLOCKED", media_type)
        if len(response.payload) > self.policy.max_bytes_per_document:
            raise SupplementalSourceError("RFC0011_DOCUMENT_BYTES_LIMIT", request.request_id)
        artifact = self.store.persist(
            response.payload,
            media_type=media_type,
            write_completed_at_utc=response.fetched_at_utc,
        )
        return DiscoveryCaptureReceiptIR.create(
            request_sha256=request.request_sha256,
            capture_artifact_sha256=artifact.artifact_sha256,
            payload_sha256=artifact.content_sha256,
            payload_bytes=artifact.byte_length,
            original_locator=request.locator,
            final_locator=response.final_locator,
            media_type=media_type,
            fetched_at_utc=response.fetched_at_utc,
        )

    def _captured_json(self, receipt: DiscoveryCaptureReceiptIR) -> dict[str, object]:
        _, payload = self.store.load_verified(receipt.payload_sha256)
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SupplementalSourceError("RFC0011_DISCOVERY_JSON_INVALID", str(exc)) from exc
        if not isinstance(value, dict):
            raise SupplementalSourceError("RFC0011_DISCOVERY_SHAPE_INVALID", "object required")
        return value

    def derive_sec_submission_candidates(
        self, receipt: DiscoveryCaptureReceiptIR
    ) -> tuple[DiscoveredSourceCandidateIR, ...]:
        """Parse only verified captured submissions bytes into primary-doc candidates."""

        payload = self._captured_json(receipt)
        cik = str(payload.get("cik") or self.policy.issuer_cik).lstrip("0") or "0"
        recent = payload.get("filings", {})
        recent = recent.get("recent", {}) if isinstance(recent, dict) else {}
        if not isinstance(recent, dict):
            raise SupplementalSourceError("RFC0011_DISCOVERY_SHAPE_INVALID", "recent filings")
        keys = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument")
        columns = {key: recent.get(key, []) for key in keys}
        if not all(isinstance(value, list) for value in columns.values()):
            raise SupplementalSourceError("RFC0011_DISCOVERY_SHAPE_INVALID", "filing columns")
        row_count = min((len(value) for value in columns.values()), default=0)
        candidates: list[DiscoveredSourceCandidateIR] = []
        cutoff = date.fromisoformat(self.policy.as_of_date)
        earliest = cutoff - timedelta(days=self.policy.discovery_lookback_days)
        for index in range(row_count):
            filing_date = str(columns["filingDate"][index])
            document_name = str(columns["primaryDocument"][index])
            accession = str(columns["accessionNumber"][index])
            form = str(columns["form"][index])
            if not filing_date or not document_name or form not in self.policy.allowed_sec_forms:
                continue
            filing_day = date.fromisoformat(filing_date)
            if not earliest <= filing_day <= cutoff:
                continue
            accession_path = accession.replace("-", "")
            locator = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}/{document_name}"
            )
            _allowed_locator(locator, self.policy)
            candidates.append(
                DiscoveredSourceCandidateIR.create(
                    source_family_id="sec_primary_document",
                    issuer_cik=cik,
                    accession_number=accession,
                    filing_date=filing_date,
                    report_date=str(columns["reportDate"][index]) or None,
                    form=form,
                    document_name=document_name,
                    locator=locator,
                    parent_discovery_receipt_sha256=receipt.receipt_sha256,
                )
            )
        if len(candidates) > self.policy.max_candidates:
            raise SupplementalSourceError("RFC0011_CANDIDATE_LIMIT", str(len(candidates)))
        return tuple(sorted(candidates, key=lambda item: item.candidate_id))

    def derive_sec_filing_intents(self, receipt: DiscoveryCaptureReceiptIR) -> SecFilingIntentSetIR:
        """Bind SEC filing intent solely to the verified submissions capture."""

        payload = self._captured_json(receipt)
        recent = payload.get("filings", {})
        recent = recent.get("recent", {}) if isinstance(recent, dict) else {}
        if not isinstance(recent, dict):
            raise SupplementalSourceError("RFC0011_DISCOVERY_SHAPE_INVALID", "recent filings")
        required = (
            "accessionNumber",
            "filingDate",
            "reportDate",
            "form",
            "primaryDocument",
        )
        optional = ("primaryDocDescription", "items")
        columns = {key: recent.get(key, []) for key in (*required, *optional)}
        if not all(isinstance(columns[key], list) for key in required):
            raise SupplementalSourceError("RFC0011_DISCOVERY_SHAPE_INVALID", "filing columns")
        row_count = min((len(columns[key]) for key in required), default=0)
        cutoff = date.fromisoformat(self.policy.as_of_date)
        earliest = cutoff - timedelta(days=self.policy.discovery_lookback_days)
        intents: list[SecFilingIntentIR] = []
        for index in range(row_count):
            filing_date = str(columns["filingDate"][index])
            form = str(columns["form"][index])
            if not filing_date or form not in self.policy.allowed_sec_forms:
                continue
            filing_day = date.fromisoformat(filing_date)
            if not earliest <= filing_day <= cutoff:
                continue
            raw_items = columns["items"][index] if index < len(columns["items"]) else ""
            tokens = re.split(r"\s*,\s*", str(raw_items).strip()) if raw_items else []
            filing_items = tuple(
                sorted({token for token in tokens if _SEC_ITEM_CODE.fullmatch(token)})
            )
            description = (
                str(columns["primaryDocDescription"][index])
                if index < len(columns["primaryDocDescription"])
                else ""
            )
            report_date = str(columns["reportDate"][index]) or None
            intent_roles = ("EARNINGS_RESULTS",) if form == "8-K" and "2.02" in filing_items else ()
            intents.append(
                SecFilingIntentIR.create(
                    accession_number=str(columns["accessionNumber"][index]),
                    filing_date=filing_date,
                    report_date=report_date,
                    form=form,
                    primary_document=str(columns["primaryDocument"][index]),
                    primary_document_description=description,
                    filing_items=filing_items,
                    intent_roles=intent_roles,
                    parent_submissions_receipt_sha256=receipt.receipt_sha256,
                )
            )
        return SecFilingIntentSetIR.create(
            policy_sha256=self.policy.policy_sha256,
            submissions_receipt_sha256=receipt.receipt_sha256,
            intents=tuple(intents),
        )

    def select_item202_index_parents(
        self,
        candidate_set: DiscoveredSourceSetIR,
        intent_set: SecFilingIntentSetIR,
        *,
        max_parents: int = 2,
        window_days: int = 14,
    ) -> tuple[SecFilingIntentIR, ...]:
        """Select bounded 8-K index parents from hash-bound exact Item 2.02 intent."""

        if candidate_set.policy_sha256 != self.policy.policy_sha256:
            raise SupplementalSourceError("RFC0011_POLICY_BINDING_MISMATCH", "candidate set")
        if intent_set.policy_sha256 != self.policy.policy_sha256:
            raise SupplementalSourceError("RFC0011_POLICY_BINDING_MISMATCH", "filing intent set")
        if not 0 <= max_parents <= 2:
            raise SupplementalSourceError("RFC0011_ITEM202_INDEX_LIMIT", str(max_parents))
        current_primary = self._current_primary(candidate_set)
        if current_primary is None:
            return ()
        primary_filing = date.fromisoformat(current_primary.filing_date)
        primary_report = (
            date.fromisoformat(current_primary.report_date) if current_primary.report_date else None
        )
        cutoff = date.fromisoformat(self.policy.as_of_date)
        eligible = [
            item
            for item in intent_set.intents
            if item.form == "8-K"
            and "EARNINGS_RESULTS" in item.intent_roles
            and date.fromisoformat(item.filing_date) <= cutoff
            and abs((date.fromisoformat(item.filing_date) - primary_filing).days) <= window_days
        ]

        def rank(item: SecFilingIntentIR) -> tuple[object, ...]:
            filing_day = date.fromisoformat(item.filing_date)
            report_distance = (
                abs((date.fromisoformat(item.report_date) - primary_report).days)
                if item.report_date and primary_report
                else 10**9
            )
            return (
                abs((filing_day - primary_filing).days),
                report_distance,
                -filing_day.toordinal(),
                item.accession_number,
            )

        return tuple(sorted(eligible, key=rank)[:max_parents])

    @staticmethod
    def _current_primary(
        candidate_set: DiscoveredSourceSetIR,
    ) -> DiscoveredSourceCandidateIR | None:
        quarterly_primaries = [
            item
            for item in candidate_set.candidates
            if item.source_family_id == "sec_primary_document"
            and item.form in {"10-Q", "10-K"}
            and not is_sec_index_page(item.document_name)
        ]
        return max(
            quarterly_primaries,
            key=lambda item: (
                item.report_date or "",
                item.filing_date,
                item.accession_number,
                item.document_name,
            ),
            default=None,
        )

    def selection_context(
        self,
        candidate_set: DiscoveredSourceSetIR,
        intent_set: SecFilingIntentSetIR,
        item202_parents: tuple[SecFilingIntentIR, ...],
    ) -> CandidateSelectionContextIR:
        if candidate_set.policy_sha256 != self.policy.policy_sha256:
            raise SupplementalSourceError("RFC0011_POLICY_BINDING_MISMATCH", "candidate set")
        if intent_set.policy_sha256 != self.policy.policy_sha256:
            raise SupplementalSourceError("RFC0011_POLICY_BINDING_MISMATCH", "filing intent set")
        current_primary = self._current_primary(candidate_set)
        parent_accessions = {item.accession_number for item in item202_parents}
        allowed_parent_hashes = {item.intent_sha256 for item in intent_set.intents}
        if any(item.intent_sha256 not in allowed_parent_hashes for item in item202_parents):
            raise SupplementalSourceError("RFC0011_INTENT_NOT_BOUND", "Item 2.02 parent")
        tags: list[tuple[str, str]] = []
        for candidate in candidate_set.candidates:
            if current_primary and candidate.candidate_id == current_primary.candidate_id:
                tag = "CURRENT_PRIMARY"
            elif candidate.accession_number in parent_accessions:
                tag = (
                    "ITEM_2_02_EXHIBIT"
                    if candidate.source_family_id == "sec_filed_exhibit"
                    else "ITEM_2_02_PARENT_PRIMARY"
                )
            elif candidate.source_family_id == "sec_filed_exhibit":
                tag = "OTHER_FILED_EXHIBIT"
            else:
                tag = "OTHER_PRIMARY"
            tags.append((candidate.candidate_id, tag))
        return CandidateSelectionContextIR.create(
            policy_sha256=self.policy.policy_sha256,
            candidate_set_sha256=candidate_set.set_sha256,
            filing_intent_set_sha256=intent_set.intent_set_sha256,
            candidate_tags=tuple(tags),
        )

    def derive_filing_index_candidates(
        self,
        receipt: DiscoveryCaptureReceiptIR,
        *,
        issuer_cik: str,
        accession_number: str,
        filing_date: str,
        report_date: str | None,
        form: str,
        primary_document: str,
    ) -> tuple[DiscoveredSourceCandidateIR, ...]:
        """Derive generic filed-exhibit candidates from captured SEC index JSON."""

        payload = self._captured_json(receipt)
        directory = payload.get("directory", {})
        items = directory.get("item", []) if isinstance(directory, dict) else []
        if not isinstance(items, list):
            raise SupplementalSourceError("RFC0011_DISCOVERY_SHAPE_INVALID", "index items")
        cik = issuer_cik.lstrip("0") or "0"
        accession_path = accession_number.replace("-", "")
        candidates: list[DiscoveredSourceCandidateIR] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            lowered = name.lower()
            if name == primary_document or not lowered.endswith((".htm", ".html", ".txt")):
                continue
            if not is_strict_filed_exhibit_name(name):
                continue
            locator = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}/{name}"
            _allowed_locator(locator, self.policy)
            candidates.append(
                DiscoveredSourceCandidateIR.create(
                    source_family_id="sec_filed_exhibit",
                    issuer_cik=cik,
                    accession_number=accession_number,
                    filing_date=filing_date,
                    report_date=report_date,
                    form=form,
                    document_name=name,
                    locator=locator,
                    parent_discovery_receipt_sha256=receipt.receipt_sha256,
                )
            )
        if len(candidates) > self.policy.max_candidates:
            raise SupplementalSourceError("RFC0011_CANDIDATE_LIMIT", str(len(candidates)))
        return tuple(sorted(candidates, key=lambda item: item.candidate_id))

    def candidate_set(
        self,
        discovery_receipts: tuple[DiscoveryCaptureReceiptIR, ...],
        candidates: tuple[DiscoveredSourceCandidateIR, ...],
    ) -> DiscoveredSourceSetIR:
        if len(candidates) > self.policy.max_candidates:
            raise SupplementalSourceError("RFC0011_CANDIDATE_LIMIT", str(len(candidates)))
        for candidate in candidates:
            if candidate.source_family_id not in self.policy.allowed_source_family_ids:
                raise SupplementalSourceError(
                    "RFC0011_SOURCE_FAMILY_BLOCKED", candidate.source_family_id
                )
            _allowed_locator(candidate.locator, self.policy)
        return DiscoveredSourceSetIR.create(
            policy_sha256=self.policy.policy_sha256,
            discovery_receipt_sha256s=tuple(item.receipt_sha256 for item in discovery_receipts),
            candidates=candidates,
        )

    def select(
        self,
        candidate_set: DiscoveredSourceSetIR,
        selection_context: CandidateSelectionContextIR | None = None,
    ) -> tuple[DiscoveredSourceCandidateIR, ...]:
        if candidate_set.policy_sha256 != self.policy.policy_sha256:
            raise SupplementalSourceError("RFC0011_POLICY_BINDING_MISMATCH", "candidate set")
        eligible = [
            item for item in candidate_set.candidates if not is_sec_index_page(item.document_name)
        ]
        current_primary = self._current_primary(candidate_set)

        if selection_context is not None:
            if selection_context.policy_sha256 != self.policy.policy_sha256:
                raise SupplementalSourceError(
                    "RFC0011_POLICY_BINDING_MISMATCH", "selection context"
                )
            if selection_context.candidate_set_sha256 != candidate_set.set_sha256:
                raise SupplementalSourceError("RFC0011_CANDIDATE_SET_MISMATCH", "selection context")
            tags = dict(selection_context.candidate_tags)
            if set(tags) != {item.candidate_id for item in candidate_set.candidates}:
                raise SupplementalSourceError(
                    "RFC0011_SELECTION_CONTEXT_INCOMPLETE", "candidate tags"
                )
            priorities = {
                "CURRENT_PRIMARY": 0,
                "ITEM_2_02_EXHIBIT": 1,
                "ITEM_2_02_PARENT_PRIMARY": 2,
                "OTHER_FILED_EXHIBIT": 3,
                "OTHER_PRIMARY": 4,
            }

            def context_rank(item: DiscoveredSourceCandidateIR) -> tuple[object, ...]:
                return (
                    priorities[tags[item.candidate_id]],
                    -(date.fromisoformat(item.report_date or item.filing_date).toordinal()),
                    -(date.fromisoformat(item.filing_date).toordinal()),
                    item.accession_number,
                    item.document_name,
                    item.candidate_id,
                )

            ordered = sorted(eligible, key=context_rank)
            return tuple(ordered[: self.policy.max_selected_documents])

        def rank(item: DiscoveredSourceCandidateIR) -> tuple[object, ...]:
            if current_primary is not None and item.candidate_id == current_primary.candidate_id:
                tier = 0
            elif (
                current_primary is not None
                and item.source_family_id == "sec_filed_exhibit"
                and is_earnings_filed_exhibit_name(item.document_name)
                and abs(
                    (
                        date.fromisoformat(item.filing_date)
                        - date.fromisoformat(current_primary.filing_date)
                    ).days
                )
                <= 7
            ):
                tier = 1
            elif item.source_family_id == "sec_filed_exhibit":
                tier = 2
            else:
                tier = 3
            return (
                tier,
                -(date.fromisoformat(item.report_date or item.filing_date).toordinal()),
                -(date.fromisoformat(item.filing_date).toordinal()),
                item.accession_number,
                item.document_name,
                item.candidate_id,
            )

        ordered = sorted(eligible, key=rank)
        selected = tuple(ordered[: self.policy.max_selected_documents])
        if len(selected) > self.policy.max_selected_documents:
            raise SupplementalSourceError("RFC0011_SELECTION_LIMIT", str(len(selected)))
        return selected

    def capture_selected(
        self,
        candidate_set: DiscoveredSourceSetIR,
        selected: tuple[DiscoveredSourceCandidateIR, ...],
        fetcher: NetworkFetcher,
    ) -> SupplementalEvidenceSetIR:
        if self.policy.network_mode != "live_acquisition":
            raise SupplementalSourceError("RFC0011_REPLAY_NETWORK_BLOCKED", "selected captures")
        if len(selected) > self.policy.max_selected_documents:
            raise SupplementalSourceError("RFC0011_SELECTION_LIMIT", str(len(selected)))
        receipts: list[SupplementalCaptureReceiptIR] = []
        allowed_ids = {item.candidate_id for item in candidate_set.candidates}
        for candidate in selected:
            if candidate.candidate_id not in allowed_ids:
                raise SupplementalSourceError(
                    "RFC0011_CANDIDATE_NOT_DISCOVERED", candidate.candidate_id
                )
            _allowed_locator(candidate.locator, self.policy)
            response = fetcher(candidate.locator)
            _allowed_locator(response.final_locator, self.policy)
            media_type = _media_type(response.media_type)
            if media_type not in self.policy.allowed_media_types:
                raise SupplementalSourceError("RFC0011_MEDIA_TYPE_BLOCKED", media_type)
            if len(response.payload) > self.policy.max_bytes_per_document:
                raise SupplementalSourceError(
                    "RFC0011_DOCUMENT_BYTES_LIMIT", candidate.candidate_id
                )
            artifact = self.store.persist(
                response.payload,
                media_type=media_type,
                write_completed_at_utc=response.fetched_at_utc,
            )
            receipts.append(
                SupplementalCaptureReceiptIR.create(
                    candidate_id=candidate.candidate_id,
                    candidate_set_sha256=candidate_set.set_sha256,
                    capture_artifact_sha256=artifact.artifact_sha256,
                    payload_sha256=artifact.content_sha256,
                    payload_bytes=artifact.byte_length,
                    original_locator=candidate.locator,
                    final_locator=response.final_locator,
                    media_type=media_type,
                    fetched_at_utc=response.fetched_at_utc,
                )
            )
        return SupplementalEvidenceSetIR.create(
            policy_sha256=self.policy.policy_sha256,
            candidate_set_sha256=candidate_set.set_sha256,
            capture_receipts=tuple(receipts),
        )

    def replay(
        self,
        candidate_set: DiscoveredSourceSetIR,
        capture_receipts: tuple[SupplementalCaptureReceiptIR, ...],
    ) -> SupplementalEvidenceSetIR:
        # Replay consumes only the already bound policy, receipts, and capture
        # store.  No fetcher is accepted by this API, so network use is
        # structurally impossible while the live evidence identity is retained.
        for receipt in capture_receipts:
            if receipt.candidate_set_sha256 != candidate_set.set_sha256:
                raise SupplementalSourceError(
                    "RFC0011_CANDIDATE_SET_MISMATCH", receipt.candidate_id
                )
            artifact, payload = self.store.load_verified(receipt.payload_sha256)
            if (
                artifact.artifact_sha256 != receipt.capture_artifact_sha256
                or len(payload) != receipt.payload_bytes
            ):
                raise SupplementalSourceError(
                    "RFC0011_CAPTURE_BINDING_MISMATCH", receipt.candidate_id
                )
        return SupplementalEvidenceSetIR.create(
            policy_sha256=self.policy.policy_sha256,
            candidate_set_sha256=candidate_set.set_sha256,
            capture_receipts=capture_receipts,
        )


STRUCTURED_REGULATORY_SOURCE_PROFILE = {
    "contract_id": "room16.rfc0011.structured_regulatory_source_profile",
    "contract_version": 1,
    "source_family_id": "structured_regulatory_dataset",
    "capture_before_parse_required": True,
    "offline_replay_required": True,
    "live_activation": False,
    "activation_gate": "official dataset inventory and dictionary hash binding",
    "supported_fixture_media_types": ["application/json", "text/csv"],
}
