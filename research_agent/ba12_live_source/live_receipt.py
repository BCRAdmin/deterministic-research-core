"""Provider execution boundary for RFC-0010 live capture."""

from __future__ import annotations

import importlib
import inspect
import json
import os
import socket
import tempfile
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from research_agent.capabilities.market_registry import get_provider_capability
from research_agent.compiler_foundation.canonical import canonical_bytes
from research_agent.semantic_compiler.source_frontend.adapter_contract import (
    verify_adapter_implementation,
)
from research_agent.semantic_compiler.source_frontend.contracts import (
    CompileRequestIR,
    SourceAcquisitionIR,
    SourceAcquisitionItemIR,
)

from .capture_store import ContentAddressedCaptureStore, sha256_bytes
from .attempt_store import LiveAttemptStore
from .contracts import (
    LiveAttemptRecord,
    LiveCaptureArtifact,
    LiveCaptureError,
    LiveRetrievalReceipt,
    fail,
)


@dataclass(frozen=True)
class ProviderResponse:
    """Raw adapter response handed only to the capture executor."""

    provider_id: str
    source_id: str
    source_type: str
    original_locator: str
    final_locator: str
    status: str
    media_type: str
    payload: bytes
    fetched_at_utc: str
    available_at_utc: str
    published_at_utc_or_null: str | None = None
    filing_date_or_null: str | None = None
    variable_cost_incurred: bool = False
    variable_cost_amount_or_null: str | None = None
    variable_cost_currency_or_null: str | None = None


@dataclass(frozen=True)
class LiveCaptureRecord:
    """Parser-safe Stage A output; raw network bytes are intentionally absent."""

    artifact: LiveCaptureArtifact
    receipt: LiveRetrievalReceipt


@dataclass(frozen=True)
class ProviderStatusClassification:
    outcome: str
    failure_class: str | None
    failure_code: str | None


def classify_provider_status(provider_id: str, raw_status: str) -> ProviderStatusClassification:
    """Fail-closed normalization shared by every live provider adapter."""

    status = raw_status.strip()
    if not status:
        return ProviderStatusClassification("failure", "malformed_response", "LIVE_STATUS_EMPTY")
    if status.isdigit():
        code = int(status)
        if 200 <= code < 300:
            return ProviderStatusClassification("success", None, None)
        mapped = {
            401: ("authentication", "LIVE_PROVIDER_AUTHENTICATION"),
            403: ("authorization", "LIVE_PROVIDER_AUTHORIZATION"),
            404: ("not_found", "LIVE_PROVIDER_NOT_FOUND"),
            429: ("rate_limited", "LIVE_PROVIDER_RATE_LIMITED"),
        }.get(code)
        failure_class, failure_code = mapped or (
            "http_error",
            "LIVE_PROVIDER_REDIRECT" if 300 <= code < 400 else "LIVE_PROVIDER_HTTP_ERROR",
        )
        return ProviderStatusClassification("failure", failure_class, failure_code)
    normalized = status.upper()
    success_by_provider = {
        "massive": {"OK", "DELAYED", "SUCCESS"},
        "sec": {"OK", "SUCCESS"},
        "nasdaq": {"OK", "SUCCESS"},
        "bse": {"OK", "SUCCESS"},
    }
    if normalized in success_by_provider.get(provider_id, {"OK", "SUCCESS"}):
        return ProviderStatusClassification("success", None, None)
    if normalized in {"UNAUTHORIZED", "AUTHENTICATION_FAILED"}:
        return ProviderStatusClassification("failure", "authentication", "LIVE_PROVIDER_AUTHENTICATION")
    if normalized in {"FORBIDDEN", "AUTHORIZATION_FAILED"}:
        return ProviderStatusClassification("failure", "authorization", "LIVE_PROVIDER_AUTHORIZATION")
    if normalized in {"RATE_LIMITED", "TOO_MANY_REQUESTS"}:
        return ProviderStatusClassification("failure", "rate_limited", "LIVE_PROVIDER_RATE_LIMITED")
    if normalized in {"NOT_FOUND", "NO_RESULTS"}:
        return ProviderStatusClassification("failure", "not_found", "LIVE_PROVIDER_NOT_FOUND")
    return ProviderStatusClassification("failure", "provider_error", "LIVE_PROVIDER_STATUS_ERROR")


def classify_adapter_exception(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, urllib.error.HTTPError):
        classified = classify_provider_status("http", str(exc.code))
        return classified.failure_class or "http_error", classified.failure_code or "LIVE_PROVIDER_HTTP_ERROR"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout", "LIVE_PROVIDER_TIMEOUT"
    if isinstance(exc, (urllib.error.URLError, ConnectionError, OSError)):
        return "network_error", "LIVE_PROVIDER_NETWORK_ERROR"
    if isinstance(exc, (ValueError, TypeError, json.JSONDecodeError)):
        return "malformed_response", "LIVE_PROVIDER_MALFORMED_RESPONSE"
    return "provider_error", "LIVE_PROVIDER_ADAPTER_ERROR"


def adapter_implementation_sha256(item: SourceAcquisitionItemIR) -> str:
    descriptor = verify_adapter_implementation(item.provider_id)
    if descriptor["implementation_ref"] != item.implementation_ref:
        raise fail("LIVE_ADAPTER_IDENTITY_MISMATCH", "plan and adapter descriptor differ")
    module_name, class_name = item.implementation_ref.split(":", 1)
    implementation = getattr(importlib.import_module(module_name), class_name)
    source_path = inspect.getsourcefile(implementation)
    if source_path is None:
        raise fail("LIVE_ADAPTER_SOURCE_MISSING", "adapter implementation source is unavailable")
    return sha256_bytes(Path(source_path).read_bytes())


class LiveCaptureExecutor:
    """Capture a provider response, verify it, then issue one authoritative receipt."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink():
            raise fail("LIVE_CAPTURE_ROOT_SYMLINK", "live capture execution root is symlinked")
        self.root = root.resolve()
        self.capture_store = ContentAddressedCaptureStore(self.root / "capture_store")
        self.attempt_store = LiveAttemptStore(self.root / "attempts")
        self.receipt_root = self.root / "receipts"
        self.receipt_root.mkdir(parents=True, exist_ok=True)
        if self.receipt_root.is_symlink():
            raise fail("LIVE_RECEIPT_ROOT_SYMLINK", "live receipt root is symlinked")

    @staticmethod
    def _acquisition(
        request: CompileRequestIR,
        plan: SourceAcquisitionIR,
        acquisition_id: str,
    ) -> SourceAcquisitionItemIR:
        if request.request_sha256 != plan.request_sha256:
            raise fail("LIVE_REQUEST_PLAN_MISMATCH", "plan belongs to another compile request")
        if request.policy.network_mode != "live_acquisition":
            raise fail("LIVE_POLICY_MODE_REQUIRED", "compile policy does not authorize live acquisition")
        matches = [item for item in plan.acquisitions if item.acquisition_id == acquisition_id]
        if len(matches) != 1:
            raise fail("LIVE_ACQUISITION_UNKNOWN", "acquisition is absent or duplicated in plan")
        item = matches[0]
        if item.retrieval_mode != "live_acquisition":
            raise fail("LIVE_PLAN_MODE_REQUIRED", "acquisition item is not live")
        if item.provider_id not in request.policy.allowed_provider_ids:
            raise fail("LIVE_PROVIDER_NOT_ALLOWED", "provider is not allowlisted")
        return item

    @staticmethod
    def _validate_response(
        request: CompileRequestIR,
        item: SourceAcquisitionItemIR,
        response: ProviderResponse,
    ) -> tuple[bool, ProviderStatusClassification]:
        if response.provider_id != item.provider_id:
            raise fail("LIVE_PROVIDER_FALLBACK_FORBIDDEN", "adapter returned another provider")
        if response.source_type not in item.allowed_source_types:
            raise fail("LIVE_SOURCE_TYPE_NOT_ALLOWED", "provider response source type is not planned")
        classification = classify_provider_status(item.provider_id, response.status)
        provider = get_provider_capability(item.provider_id)
        possible_cost = provider["variableCost"] == "possible"
        approved = item.provider_id in request.policy.approved_paid_provider_ids
        if possible_cost and not approved:
            raise fail("LIVE_PAID_PROVIDER_NOT_APPROVED", "paid provider lacks explicit approval")
        if response.variable_cost_incurred and not approved:
            raise fail("LIVE_PAID_PROVIDER_NOT_APPROVED", "incurred variable cost lacks approval")
        if response.variable_cost_incurred and (
            response.variable_cost_amount_or_null is None
            or response.variable_cost_currency_or_null is None
        ):
            raise fail("LIVE_COST_RECEIPT_INCOMPLETE", "incurred cost lacks amount or currency")
        if not response.payload:
            raise fail("LIVE_CAPTURE_EMPTY", "provider response is empty")
        return approved, classification

    def _receipt_path(self, request_sha256: str, acquisition_id: str, attempt_id: str) -> Path:
        identity = sha256_bytes(
            f"{request_sha256}\0{acquisition_id}\0{attempt_id}".encode("utf-8")
        )
        return self.receipt_root / f"{identity}.json"

    @staticmethod
    def _persist_once(path: Path, payload: bytes) -> None:
        if path.is_symlink():
            raise fail("LIVE_RECEIPT_PATH_SYMLINK", "live receipt path is symlinked")
        if path.exists():
            if path.read_bytes() != payload:
                raise fail(
                    "LIVE_DUPLICATE_ATTEMPT_CONFLICT",
                    "acquisition attempt already has a different authoritative receipt",
                )
            return
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".receipt-", dir=path.parent, delete=False
            ) as handle:
                temporary_name = handle.name
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, path, follow_symlinks=False)
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise fail(
                        "LIVE_DUPLICATE_ATTEMPT_CONFLICT",
                        "concurrent acquisition attempt produced a conflicting receipt",
                    )
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
        path.chmod(0o444)

    def finalize_receipt(
        self,
        *,
        request: CompileRequestIR,
        plan: SourceAcquisitionIR,
        acquisition_id: str,
        attempt_id: str,
        response: ProviderResponse,
        artifact: LiveCaptureArtifact,
    ) -> LiveCaptureRecord:
        item = self._acquisition(request, plan, acquisition_id)
        paid_approval, classification = self._validate_response(request, item, response)
        if classification.outcome != "success":
            raise fail(
                classification.failure_code or "LIVE_PROVIDER_STATUS_ERROR",
                "provider response status is not successful",
            )
        if artifact.content_sha256 != sha256_bytes(response.payload) or (
            artifact.byte_length != len(response.payload)
        ) or artifact.media_type != response.media_type:
            raise fail("LIVE_CAPTURE_RESPONSE_MISMATCH", "artifact differs from provider bytes")
        receipt = LiveRetrievalReceipt.create(
            request_sha256=request.request_sha256,
            acquisition_plan_sha256=plan.plan_sha256,
            acquisition_id=acquisition_id,
            attempt_id=attempt_id,
            provider_id=item.provider_id,
            adapter_id=item.adapter_id,
            adapter_contract_version=item.adapter_contract_version,
            adapter_implementation_sha256=adapter_implementation_sha256(item),
            source_id=response.source_id,
            source_type=response.source_type,
            original_locator=response.original_locator,
            final_locator=response.final_locator,
            http_status_or_provider_status=response.status,
            normalized_outcome="success",
            media_type=response.media_type,
            payload_sha256=artifact.content_sha256,
            payload_bytes=artifact.byte_length,
            request_as_of_date=request.as_of_date,
            fetched_at_utc=response.fetched_at_utc,
            available_at_utc=response.available_at_utc,
            published_at_utc_or_null=response.published_at_utc_or_null,
            filing_date_or_null=response.filing_date_or_null,
            availability_basis="public_timestamp",
            variable_cost_incurred=response.variable_cost_incurred,
            variable_cost_amount_or_null=response.variable_cost_amount_or_null,
            variable_cost_currency_or_null=response.variable_cost_currency_or_null,
            paid_provider_approval_bound=paid_approval,
            capture_artifact_sha256=artifact.artifact_sha256,
        )
        encoded = canonical_bytes(receipt.model_dump(mode="json"))
        self._persist_once(
            self._receipt_path(request.request_sha256, acquisition_id, attempt_id),
            encoded,
        )
        return LiveCaptureRecord(artifact=artifact, receipt=receipt)

    def _attempt_values(
        self,
        *,
        request: CompileRequestIR,
        plan: SourceAcquisitionIR,
        item: SourceAcquisitionItemIR,
        attempt_id: str,
    ) -> dict[str, object]:
        return {
            "request_sha256": request.request_sha256,
            "acquisition_plan_sha256": plan.plan_sha256,
            "acquisition_id": item.acquisition_id,
            "attempt_id": attempt_id,
            "provider_id": item.provider_id,
            "adapter_id": item.adapter_id,
            "adapter_implementation_sha256": adapter_implementation_sha256(item),
        }

    def _prepared_attempt(
        self,
        *,
        request: CompileRequestIR,
        plan: SourceAcquisitionIR,
        item: SourceAcquisitionItemIR,
        attempt_id: str,
        response: ProviderResponse,
    ) -> LiveAttemptRecord:
        return LiveAttemptRecord.create(
            **self._attempt_values(
                request=request, plan=plan, item=item, attempt_id=attempt_id
            ),
            terminal_state="prepared_capture",
            source_id_or_null=response.source_id,
            source_type_or_null=response.source_type,
            original_locator_or_null=response.original_locator,
            final_locator_or_null=response.final_locator,
            raw_status_or_null=response.status,
            normalized_outcome="success",
            media_type_or_null=response.media_type,
            fetched_at_utc_or_null=response.fetched_at_utc,
            available_at_utc_or_null=response.available_at_utc,
            published_at_utc_or_null=response.published_at_utc_or_null,
            filing_date_or_null=response.filing_date_or_null,
            variable_cost_incurred=response.variable_cost_incurred,
            variable_cost_amount_or_null=response.variable_cost_amount_or_null,
            variable_cost_currency_or_null=response.variable_cost_currency_or_null,
            payload_sha256_or_null=sha256_bytes(response.payload),
            payload_bytes_or_null=len(response.payload),
        )

    def _failure_attempt(
        self,
        *,
        request: CompileRequestIR,
        plan: SourceAcquisitionIR,
        item: SourceAcquisitionItemIR,
        attempt_id: str,
        failure_class: str,
        failure_code: str,
        response: ProviderResponse | None = None,
    ) -> LiveAttemptRecord:
        return LiveAttemptRecord.create(
            **self._attempt_values(
                request=request, plan=plan, item=item, attempt_id=attempt_id
            ),
            terminal_state="failed",
            source_id_or_null=response.source_id if response else None,
            source_type_or_null=response.source_type if response else None,
            original_locator_or_null=response.original_locator if response else None,
            final_locator_or_null=response.final_locator if response else None,
            raw_status_or_null=response.status if response else None,
            normalized_outcome="failure",
            media_type_or_null=response.media_type if response else None,
            fetched_at_utc_or_null=response.fetched_at_utc if response else None,
            available_at_utc_or_null=response.available_at_utc if response else None,
            published_at_utc_or_null=response.published_at_utc_or_null if response else None,
            filing_date_or_null=response.filing_date_or_null if response else None,
            variable_cost_incurred=response.variable_cost_incurred if response else False,
            variable_cost_amount_or_null=(response.variable_cost_amount_or_null if response else None),
            variable_cost_currency_or_null=(response.variable_cost_currency_or_null if response else None),
            payload_sha256_or_null=None,
            payload_bytes_or_null=None,
            failure_class_or_null=failure_class,
            failure_code_or_null=failure_code,
        )

    def _success_attempt(
        self,
        *,
        prepared: LiveAttemptRecord,
        record: LiveCaptureRecord,
    ) -> LiveAttemptRecord:
        body = prepared.model_dump(mode="json")
        for key in ("contract_id", "contract_version", "record_sha256"):
            body.pop(key)
        body.update(
            terminal_state="captured_success",
            capture_artifact_sha256_or_null=record.artifact.artifact_sha256,
            live_receipt_sha256_or_null=record.receipt.receipt_sha256,
        )
        return LiveAttemptRecord.create(**body)

    def prepare_capture(
        self,
        *,
        request: CompileRequestIR,
        plan: SourceAcquisitionIR,
        acquisition_id: str,
        attempt_id: str,
        response: ProviderResponse,
    ) -> LiveAttemptRecord:
        """Durably bind successful response provenance before storing response bytes."""

        item = self._acquisition(request, plan, acquisition_id)
        _, classification = self._validate_response(request, item, response)
        if classification.outcome != "success":
            raise fail(
                classification.failure_code or "LIVE_PROVIDER_STATUS_ERROR",
                "provider response status is not successful",
            )
        return self.attempt_store.persist(
            self._prepared_attempt(
                request=request,
                plan=plan,
                item=item,
                attempt_id=attempt_id,
                response=response,
            )
        )

    def load_receipt(
        self, request_sha256: str, acquisition_id: str, attempt_id: str
    ) -> LiveRetrievalReceipt:
        path = self._receipt_path(request_sha256, acquisition_id, attempt_id)
        if path.is_symlink() or not path.is_file():
            raise fail("LIVE_RECEIPT_MISSING", "durable live receipt is missing")
        try:
            receipt = LiveRetrievalReceipt.model_validate(json.loads(path.read_bytes()))
        except (json.JSONDecodeError, ValueError) as exc:
            raise fail("LIVE_RECEIPT_INVALID", "durable live receipt failed verification") from exc
        if (
            receipt.request_sha256 != request_sha256
            or receipt.acquisition_id != acquisition_id
            or receipt.attempt_id != attempt_id
        ):
            raise fail("LIVE_RECEIPT_IDENTITY_MISMATCH", "receipt path and identity differ")
        return receipt

    def load_successful_record(
        self, *, request_sha256: str, acquisition_id: str, attempt_id: str
    ) -> LiveCaptureRecord:
        attempt = self.attempt_store.load(
            request_sha256=request_sha256,
            acquisition_id=acquisition_id,
            attempt_id=attempt_id,
            terminal_only=True,
        )
        if attempt.terminal_state != "captured_success":
            raise fail("LIVE_ATTEMPT_NOT_SUCCESSFUL", "attempt did not produce source authority")
        receipt = self.load_receipt(request_sha256, acquisition_id, attempt_id)
        artifact, _ = self.capture_store.load_verified(receipt.payload_sha256)
        if (
            attempt.live_receipt_sha256_or_null != receipt.receipt_sha256
            or attempt.capture_artifact_sha256_or_null != artifact.artifact_sha256
            or receipt.capture_artifact_sha256 != artifact.artifact_sha256
        ):
            raise fail("LIVE_ATTEMPT_GRAPH_MISMATCH", "attempt, receipt and capture differ")
        return LiveCaptureRecord(artifact=artifact, receipt=receipt)

    def recover_attempt(
        self,
        *,
        request: CompileRequestIR,
        plan: SourceAcquisitionIR,
        acquisition_id: str,
        attempt_id: str,
    ) -> LiveCaptureRecord:
        """Recover solely from persisted prepared/terminal authority and capture bytes."""

        item = self._acquisition(request, plan, acquisition_id)
        attempt = self.attempt_store.load(
            request_sha256=request.request_sha256,
            acquisition_id=acquisition_id,
            attempt_id=attempt_id,
        )
        if attempt.acquisition_plan_sha256 != plan.plan_sha256:
            raise fail("LIVE_ATTEMPT_PLAN_MISMATCH", "attempt belongs to another plan")
        if attempt.terminal_state == "captured_success":
            return self.load_successful_record(
                request_sha256=request.request_sha256,
                acquisition_id=acquisition_id,
                attempt_id=attempt_id,
            )
        if attempt.terminal_state == "failed":
            raise fail("LIVE_ATTEMPT_NOT_SUCCESSFUL", "failed attempt cannot become source evidence")
        if attempt.payload_sha256_or_null is None:
            raise fail("LIVE_PREPARED_PAYLOAD_MISSING", "prepared attempt has no payload hash")
        artifact, payload = self.capture_store.load_verified(attempt.payload_sha256_or_null)
        response = ProviderResponse(
            provider_id=attempt.provider_id,
            source_id=attempt.source_id_or_null or "",
            source_type=attempt.source_type_or_null or "",
            original_locator=attempt.original_locator_or_null or "",
            final_locator=attempt.final_locator_or_null or "",
            status=attempt.raw_status_or_null or "",
            media_type=attempt.media_type_or_null or "",
            payload=payload,
            fetched_at_utc=attempt.fetched_at_utc_or_null or "",
            available_at_utc=attempt.available_at_utc_or_null or "",
            published_at_utc_or_null=attempt.published_at_utc_or_null,
            filing_date_or_null=attempt.filing_date_or_null,
            variable_cost_incurred=attempt.variable_cost_incurred,
            variable_cost_amount_or_null=attempt.variable_cost_amount_or_null,
            variable_cost_currency_or_null=attempt.variable_cost_currency_or_null,
        )
        record = self.finalize_receipt(
            request=request,
            plan=plan,
            acquisition_id=acquisition_id,
            attempt_id=attempt_id,
            response=response,
            artifact=artifact,
        )
        self.attempt_store.persist(self._success_attempt(prepared=attempt, record=record))
        return record

    def capture(
        self,
        *,
        request: CompileRequestIR,
        plan: SourceAcquisitionIR,
        acquisition_id: str,
        attempt_id: str,
        adapter: Callable[[], ProviderResponse],
    ) -> LiveCaptureRecord:
        item = self._acquisition(request, plan, acquisition_id)
        try:
            response = adapter()
        except Exception as exc:
            failure_class, failure_code = classify_adapter_exception(exc)
            self.attempt_store.persist(
                self._failure_attempt(
                    request=request,
                    plan=plan,
                    item=item,
                    attempt_id=attempt_id,
                    failure_class=failure_class,
                    failure_code=failure_code,
                )
            )
            raise fail(failure_code, "provider adapter execution failed") from exc
        _, classification = self._validate_response(request, item, response)
        if classification.outcome != "success":
            self.attempt_store.persist(
                self._failure_attempt(
                    request=request,
                    plan=plan,
                    item=item,
                    attempt_id=attempt_id,
                    response=response,
                    failure_class=classification.failure_class or "provider_error",
                    failure_code=classification.failure_code or "LIVE_PROVIDER_STATUS_ERROR",
                )
            )
            raise fail(
                classification.failure_code or "LIVE_PROVIDER_STATUS_ERROR",
                "provider response status is not successful",
            )
        prepared = self.prepare_capture(
            request=request,
            plan=plan,
            acquisition_id=acquisition_id,
            attempt_id=attempt_id,
            response=response,
        )
        # This is the only call site that receives response.payload.  All later
        # stages receive a verified immutable artifact reference instead.
        artifact = self.capture_store.persist(
            response.payload,
            media_type=response.media_type,
            write_completed_at_utc=response.fetched_at_utc,
        )
        record = self.finalize_receipt(
            request=request,
            plan=plan,
            acquisition_id=acquisition_id,
            attempt_id=attempt_id,
            response=response,
            artifact=artifact,
        )
        self.attempt_store.persist(self._success_attempt(prepared=prepared, record=record))
        return record
