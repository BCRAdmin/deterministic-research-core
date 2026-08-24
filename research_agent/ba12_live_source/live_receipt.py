"""Provider execution boundary for RFC-0010 live capture."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
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
from .contracts import LiveCaptureArtifact, LiveRetrievalReceipt, fail


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
    ) -> bool:
        if response.provider_id != item.provider_id:
            raise fail("LIVE_PROVIDER_FALLBACK_FORBIDDEN", "adapter returned another provider")
        if response.source_type not in item.allowed_source_types:
            raise fail("LIVE_SOURCE_TYPE_NOT_ALLOWED", "provider response source type is not planned")
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
        return approved

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
        paid_approval = self._validate_response(request, item, response)
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
        response = adapter()
        self._validate_response(request, item, response)
        # This is the only call site that receives response.payload.  All later
        # stages receive a verified immutable artifact reference instead.
        artifact = self.capture_store.persist(
            response.payload,
            media_type=response.media_type,
            write_completed_at_utc=response.fetched_at_utc,
        )
        return self.finalize_receipt(
            request=request,
            plan=plan,
            acquisition_id=acquisition_id,
            attempt_id=attempt_id,
            response=response,
            artifact=artifact,
        )
