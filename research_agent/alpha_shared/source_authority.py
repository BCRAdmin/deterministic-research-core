"""Capture-first RFC-0011 discovery, selection, capture, and replay."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from pathlib import PurePosixPath
from typing import Callable
from urllib.parse import unquote, urlparse

from research_agent.ba12_live_source.capture_store import ContentAddressedCaptureStore

from .contracts import (
    CandidateSelectionContextIR,
    CandidateSelectionContextV3IR,
    DiscoveryCaptureReceiptIR,
    DiscoveryRequestIR,
    DiscoveredSourceCandidateIR,
    DiscoveredSourceSetIR,
    ReferencedExhibitCandidateBindingIR,
    SecExhibitReferenceIR,
    SecExhibitReferenceSetIR,
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
_EXHIBIT_NUMBER = re.compile(r"(?<![0-9])99\.([0-9]+)(?![0-9])")
_REFERENCE_EXTENSION = {".htm", ".html", ".txt"}


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


def _safe_exhibit_href(href: str) -> str:
    """Return a safe same-directory SEC exhibit name or fail closed."""

    value = href.strip()
    parsed = urlparse(value)
    path = PurePosixPath(parsed.path)
    if (
        not value
        or unquote(value) != value
        or parsed.scheme
        or parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path.startswith("/")
        or ".." in path.parts
        or len(path.parts) != 1
        or path.suffix.lower() not in _REFERENCE_EXTENSION
        or is_sec_index_page(path.name)
    ):
        raise SupplementalSourceError("REIT_EXHIBIT_REFERENCE_HREF_UNSAFE", href)
    return path.name


class _ExhibitReferenceHTMLParser(HTMLParser):
    """Collect anchors within their structural table row."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str, tuple[dict[str, object], ...]]] = []
        self._in_row = False
        self._row_text: list[str] = []
        self._anchors: list[dict[str, object]] = []
        self._anchor: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered == "tr":
            self._in_row = True
            self._row_text = []
            self._anchors = []
            self._anchor = None
        elif lowered == "a" and self._in_row:
            values = {key.casefold(): value or "" for key, value in attrs}
            self._anchor = {
                "href": values.get("href", ""),
                "sec_extract": "-sec-extract:exhibit" in values.get("style", "").casefold(),
                "text": [],
            }

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "a" and self._anchor is not None:
            self._anchor["text"] = " ".join(self._anchor["text"]).strip()
            self._anchors.append(self._anchor)
            self._anchor = None
        elif lowered == "tr" and self._in_row:
            text = " ".join(" ".join(self._row_text).split())
            self.rows.append((text, tuple(self._anchors)))
            self._in_row = False

    def handle_data(self, data: str) -> None:
        if self._in_row:
            self._row_text.append(data)
        if self._anchor is not None:
            self._anchor["text"].append(data)


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

    def derive_sec_exhibit_references(
        self,
        *,
        parent_intent: SecFilingIntentIR,
        parent_candidate: DiscoveredSourceCandidateIR,
        parent_capture: SupplementalCaptureReceiptIR,
    ) -> SecExhibitReferenceSetIR:
        """Parse explicit 99.x references only from a verified captured parent 8-K."""

        if (
            parent_intent.form != "8-K"
            or parent_intent.intent_roles != ("EARNINGS_RESULTS",)
            or parent_intent.accession_number != parent_candidate.accession_number
            or parent_intent.primary_document != parent_candidate.document_name
            or parent_candidate.source_family_id != "sec_primary_document"
        ):
            raise SupplementalSourceError(
                "REIT_EXHIBIT_REFERENCE_PARENT_INTENT_MISMATCH", parent_candidate.candidate_id
            )
        if parent_capture.candidate_id != parent_candidate.candidate_id:
            raise SupplementalSourceError(
                "REIT_EXHIBIT_REFERENCE_PARENT_CAPTURE_MISMATCH", parent_capture.candidate_id
            )
        artifact, payload = self.store.load_verified(parent_capture.payload_sha256)
        if (
            artifact.artifact_sha256 != parent_capture.capture_artifact_sha256
            or len(payload) != parent_capture.payload_bytes
        ):
            raise SupplementalSourceError(
                "REIT_EXHIBIT_REFERENCE_PARENT_CAPTURE_MISMATCH", parent_capture.candidate_id
            )
        try:
            html = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SupplementalSourceError(
                "REIT_EXHIBIT_REFERENCE_PARENT_HTML_INVALID", str(exc)
            ) from exc
        parser = _ExhibitReferenceHTMLParser()
        parser.feed(html)
        references: dict[tuple[str, str], SecExhibitReferenceIR] = {}
        base_locator = parent_candidate.locator.rsplit("/", 1)[0]
        for row_text, anchors in parser.rows:
            numbers = sorted(
                {f"99.{match.group(1)}" for match in _EXHIBIT_NUMBER.finditer(row_text)},
                key=lambda value: (int(value.split(".", 1)[1]), value),
            )
            if not numbers:
                continue
            href_groups: dict[str, list[dict[str, object]]] = {}
            for anchor in anchors:
                href = str(anchor["href"])
                if href:
                    href_groups.setdefault(href, []).append(anchor)
            for raw_href, group in href_groups.items():
                anchor_numbers = {
                    f"99.{match.group(1)}"
                    for anchor in group
                    for match in _EXHIBIT_NUMBER.finditer(str(anchor["text"]))
                }
                exhibit_number = min(
                    anchor_numbers or set(numbers),
                    key=lambda value: (int(value.split(".", 1)[1]), value),
                )
                name = _safe_exhibit_href(raw_href)
                locator = f"{base_locator}/{name}"
                _allowed_locator(locator, self.policy)
                descriptions = [
                    str(anchor["text"]).strip()
                    for anchor in group
                    if str(anchor["text"]).strip()
                    and not _EXHIBIT_NUMBER.fullmatch(str(anchor["text"]).strip())
                ]
                description = max(descriptions, key=len, default=row_text).strip()
                reference = SecExhibitReferenceIR.create(
                    parent_accession_number=parent_intent.accession_number,
                    parent_filing_intent_sha256=parent_intent.intent_sha256,
                    parent_document_sha256=parent_capture.payload_sha256,
                    parent_document_name=parent_candidate.document_name,
                    exhibit_number=exhibit_number,
                    referenced_href=raw_href,
                    referenced_document_name=name,
                    description=description,
                    reference_locator=locator,
                    sec_extract_exhibit_attribute=any(bool(item["sec_extract"]) for item in group),
                    reference_role="ITEM_2_02_EXHIBIT_REFERENCE",
                )
                references[(exhibit_number, name)] = reference
        return SecExhibitReferenceSetIR.create(
            policy_sha256=self.policy.policy_sha256,
            parent_filing_intent_sha256=parent_intent.intent_sha256,
            parent_document_sha256=parent_capture.payload_sha256,
            references=tuple(references.values()),
        )

    def derive_referenced_exhibit_candidates(
        self,
        *,
        parent_intent: SecFilingIntentIR,
        reference_set: SecExhibitReferenceSetIR,
        filing_index_receipt: DiscoveryCaptureReceiptIR,
        issuer_cik: str,
    ) -> tuple[
        tuple[DiscoveredSourceCandidateIR, ...],
        tuple[ReferencedExhibitCandidateBindingIR, ...],
    ]:
        """Bind explicit references to exact same-accession captured-index membership."""

        if (
            reference_set.policy_sha256 != self.policy.policy_sha256
            or reference_set.parent_filing_intent_sha256 != parent_intent.intent_sha256
        ):
            raise SupplementalSourceError(
                "REIT_EXHIBIT_REFERENCE_SET_BINDING_MISMATCH", parent_intent.accession_number
            )
        cik = issuer_cik.lstrip("0") or "0"
        accession_path = parent_intent.accession_number.replace("-", "")
        expected_index = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}/index.json"
        )
        if (
            filing_index_receipt.original_locator != expected_index
            or filing_index_receipt.final_locator != expected_index
        ):
            raise SupplementalSourceError(
                "REIT_EXHIBIT_REFERENCE_CROSS_ACCESSION_INDEX", filing_index_receipt.original_locator
            )
        payload = self._captured_json(filing_index_receipt)
        directory = payload.get("directory", {})
        items = directory.get("item", []) if isinstance(directory, dict) else []
        if not isinstance(items, list):
            raise SupplementalSourceError("RFC0011_DISCOVERY_SHAPE_INVALID", "index items")
        inventory = {
            str(item.get("name") or "")
            for item in items
            if isinstance(item, dict) and str(item.get("name") or "")
        }
        candidates: list[DiscoveredSourceCandidateIR] = []
        bindings: list[ReferencedExhibitCandidateBindingIR] = []
        for reference in reference_set.references:
            name = _safe_exhibit_href(reference.referenced_href)
            if (
                reference.parent_accession_number != parent_intent.accession_number
                or reference.parent_filing_intent_sha256 != parent_intent.intent_sha256
                or name != reference.referenced_document_name
                or name not in inventory
                or is_sec_index_page(name)
            ):
                raise SupplementalSourceError(
                    "REIT_EXHIBIT_REFERENCE_INDEX_MEMBERSHIP_MISSING", name
                )
            locator = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}/{name}"
            if locator != reference.reference_locator:
                raise SupplementalSourceError(
                    "REIT_EXHIBIT_REFERENCE_LOCATOR_MISMATCH", locator
                )
            candidate = DiscoveredSourceCandidateIR.create(
                source_family_id="sec_filed_exhibit",
                issuer_cik=cik,
                accession_number=parent_intent.accession_number,
                filing_date=parent_intent.filing_date,
                report_date=parent_intent.report_date,
                form=parent_intent.form,
                document_name=name,
                locator=locator,
                parent_discovery_receipt_sha256=filing_index_receipt.receipt_sha256,
            )
            candidates.append(candidate)
            bindings.append(
                ReferencedExhibitCandidateBindingIR.create(
                    candidate_id=candidate.candidate_id,
                    candidate_sha256=candidate.candidate_sha256,
                    exhibit_reference_sha256=reference.reference_sha256,
                    index_receipt_sha256=filing_index_receipt.receipt_sha256,
                    exhibit_number=reference.exhibit_number,
                )
            )
        ordered = sorted(zip(candidates, bindings), key=lambda item: item[0].candidate_id)
        return tuple(item[0] for item in ordered), tuple(item[1] for item in ordered)

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

    def selection_context_v3(
        self,
        candidate_set: DiscoveredSourceSetIR,
        intent_set: SecFilingIntentSetIR,
        item202_parents: tuple[SecFilingIntentIR, ...],
        reference_sets: tuple[SecExhibitReferenceSetIR, ...],
        reference_bindings: tuple[ReferencedExhibitCandidateBindingIR, ...],
    ) -> CandidateSelectionContextV3IR:
        if candidate_set.policy_sha256 != self.policy.policy_sha256:
            raise SupplementalSourceError("RFC0011_POLICY_BINDING_MISMATCH", "candidate set")
        if intent_set.policy_sha256 != self.policy.policy_sha256:
            raise SupplementalSourceError("RFC0011_POLICY_BINDING_MISMATCH", "filing intent set")
        candidates = {item.candidate_id: item for item in candidate_set.candidates}
        references = {
            item.reference_sha256: item
            for reference_set in reference_sets
            for item in reference_set.references
        }
        binding_map = {item.candidate_id: item for item in reference_bindings}
        if len(binding_map) != len(reference_bindings):
            raise SupplementalSourceError("REIT_EXHIBIT_REFERENCE_BINDING_DUPLICATE", "candidate")
        for binding in reference_bindings:
            candidate = candidates.get(binding.candidate_id)
            reference = references.get(binding.exhibit_reference_sha256)
            if (
                candidate is None
                or reference is None
                or candidate.candidate_sha256 != binding.candidate_sha256
                or candidate.document_name != reference.referenced_document_name
                or candidate.accession_number != reference.parent_accession_number
                or binding.exhibit_number != reference.exhibit_number
            ):
                raise SupplementalSourceError(
                    "REIT_EXHIBIT_REFERENCE_CANDIDATE_BINDING_MISMATCH", binding.candidate_id
                )
        current_primary = self._current_primary(candidate_set)
        parent_accessions = {item.accession_number for item in item202_parents}
        allowed_parent_hashes = {item.intent_sha256 for item in intent_set.intents}
        if any(item.intent_sha256 not in allowed_parent_hashes for item in item202_parents):
            raise SupplementalSourceError("RFC0011_INTENT_NOT_BOUND", "Item 2.02 parent")
        tags: list[tuple[str, str]] = []
        for candidate in candidate_set.candidates:
            if current_primary and candidate.candidate_id == current_primary.candidate_id:
                tag = "CURRENT_PRIMARY"
            elif candidate.candidate_id in binding_map:
                tag = "ITEM_2_02_REFERENCED_EXHIBIT"
            elif (
                candidate.accession_number in parent_accessions
                and candidate.source_family_id == "sec_primary_document"
            ):
                tag = "ITEM_2_02_PARENT_PRIMARY"
            elif candidate.source_family_id == "sec_filed_exhibit":
                tag = "OTHER_FILED_EXHIBIT"
            else:
                tag = "OTHER_PRIMARY"
            tags.append((candidate.candidate_id, tag))
        return CandidateSelectionContextV3IR.create(
            policy_sha256=self.policy.policy_sha256,
            candidate_set_sha256=candidate_set.set_sha256,
            filing_intent_set_sha256=intent_set.intent_set_sha256,
            exhibit_reference_set_sha256s=tuple(
                item.reference_set_sha256 for item in reference_sets
            ),
            reference_candidate_bindings=reference_bindings,
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
        selection_context: CandidateSelectionContextIR | CandidateSelectionContextV3IR | None = None,
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
            priorities = (
                {
                    "CURRENT_PRIMARY": 0,
                    "ITEM_2_02_REFERENCED_EXHIBIT": 1,
                    "ITEM_2_02_PARENT_PRIMARY": 2,
                    "OTHER_FILED_EXHIBIT": 3,
                    "OTHER_PRIMARY": 4,
                }
                if isinstance(selection_context, CandidateSelectionContextV3IR)
                else {
                    "CURRENT_PRIMARY": 0,
                    "ITEM_2_02_EXHIBIT": 1,
                    "ITEM_2_02_PARENT_PRIMARY": 2,
                    "OTHER_FILED_EXHIBIT": 3,
                    "OTHER_PRIMARY": 4,
                }
            )
            reference_order = (
                {
                    item.candidate_id: (
                        int(item.exhibit_number.split(".", 1)[1]),
                        item.candidate_id,
                    )
                    for item in selection_context.reference_candidate_bindings
                }
                if isinstance(selection_context, CandidateSelectionContextV3IR)
                else {}
            )

            def context_rank(item: DiscoveredSourceCandidateIR) -> tuple[object, ...]:
                return (
                    priorities[tags[item.candidate_id]],
                    reference_order.get(item.candidate_id, (10**9, item.candidate_id)),
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
