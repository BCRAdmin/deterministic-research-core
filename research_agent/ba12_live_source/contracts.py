"""RFC-0010 additive live-capture provenance contracts.

These contracts live upstream of the frozen BA3 source front end.  They never
change, extend, or reinterpret the frozen compiler IR schema set.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"
STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]*$"


class LiveCaptureError(RuntimeError):
    """Fail-closed RFC-0010 error carrying a stable diagnostic code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def fail(code: str, message: str) -> LiveCaptureError:
    return LiveCaptureError(code, message)


def _utc_timestamp(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return value


def _domain_hash(domain: str, body: dict[str, object]) -> str:
    return sha256_json({"domain": domain, "body": body})


def _model_body(model: StrictModel, hash_field: str) -> dict[str, object]:
    body = model.model_dump(mode="json")
    body.pop(hash_field)
    return body


class LiveCaptureArtifact(StrictModel):
    contract_id: Literal["room16.ba12.live_capture_artifact"] = (
        "room16.ba12.live_capture_artifact"
    )
    contract_version: Literal[1] = 1
    artifact_id: str = Field(pattern=STABLE_ID_PATTERN)
    content_sha256: str = Field(pattern=SHA256_PATTERN)
    byte_length: int = Field(ge=1)
    media_type: str = Field(min_length=3, max_length=128)
    content_addressed_relative_path: str = Field(
        pattern=r"^captures/sha256/[0-9a-f]{2}/[0-9a-f]{64}$"
    )
    write_completed_at_utc: str
    readback_sha256: str = Field(pattern=SHA256_PATTERN)
    readback_byte_length: int = Field(ge=1)
    immutable: Literal[True] = True
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def create(
        cls,
        *,
        content_sha256: str,
        byte_length: int,
        media_type: str,
        content_addressed_relative_path: str,
        write_completed_at_utc: str,
        readback_sha256: str,
        readback_byte_length: int,
    ) -> "LiveCaptureArtifact":
        body: dict[str, object] = {
            "artifact_id": f"capture.{content_sha256}",
            "byte_length": byte_length,
            "content_addressed_relative_path": content_addressed_relative_path,
            "content_sha256": content_sha256,
            "contract_id": "room16.ba12.live_capture_artifact",
            "contract_version": 1,
            "immutable": True,
            "media_type": media_type,
            "readback_byte_length": readback_byte_length,
            "readback_sha256": readback_sha256,
            "write_completed_at_utc": write_completed_at_utc,
        }
        return cls(**body, artifact_sha256=_domain_hash("room16.ba12.live_capture_artifact@1", body))

    @model_validator(mode="after")
    def valid_artifact(self) -> "LiveCaptureArtifact":
        _utc_timestamp(self.write_completed_at_utc, "write_completed_at_utc")
        expected_path = f"captures/sha256/{self.content_sha256[:2]}/{self.content_sha256}"
        if self.content_addressed_relative_path != expected_path:
            raise ValueError("capture path does not match content hash")
        if self.readback_sha256 != self.content_sha256:
            raise ValueError("capture readback hash mismatch")
        if self.readback_byte_length != self.byte_length:
            raise ValueError("capture readback size mismatch")
        expected = _domain_hash(
            "room16.ba12.live_capture_artifact@1",
            _model_body(self, "artifact_sha256"),
        )
        if self.artifact_sha256 != expected:
            raise ValueError("capture artifact self-hash mismatch")
        return self


class LiveRetrievalReceipt(StrictModel):
    contract_id: Literal["room16.ba12.live_retrieval_receipt"] = (
        "room16.ba12.live_retrieval_receipt"
    )
    contract_version: Literal[1] = 1
    receipt_id: str = Field(pattern=STABLE_ID_PATTERN)
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    acquisition_plan_sha256: str = Field(pattern=SHA256_PATTERN)
    acquisition_id: str = Field(pattern=STABLE_ID_PATTERN)
    attempt_id: str = Field(pattern=STABLE_ID_PATTERN)
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    adapter_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    adapter_contract_version: Literal[1] = 1
    adapter_implementation_sha256: str = Field(pattern=SHA256_PATTERN)
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    source_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    original_locator: str = Field(min_length=1)
    final_locator: str = Field(min_length=1)
    transport: Literal["live_acquisition"] = "live_acquisition"
    http_status_or_provider_status: str = Field(min_length=1, max_length=128)
    media_type: str = Field(min_length=3, max_length=128)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    payload_bytes: int = Field(ge=1)
    request_as_of_date: str
    fetched_at_utc: str
    available_at_utc: str
    published_at_utc_or_null: str | None = None
    filing_date_or_null: str | None = None
    availability_basis: Literal["public_timestamp"] = "public_timestamp"
    variable_cost_incurred: bool
    variable_cost_amount_or_null: str | None = Field(default=None, pattern=r"^[0-9]+(\.[0-9]+)?$")
    variable_cost_currency_or_null: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    paid_provider_approval_bound: bool
    capture_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def create(cls, **values: object) -> "LiveRetrievalReceipt":
        seed = {
            "acquisition_id": values["acquisition_id"],
            "attempt_id": values["attempt_id"],
            "payload_sha256": values["payload_sha256"],
            "request_sha256": values["request_sha256"],
        }
        receipt_id = f"live-receipt.{sha256_json(seed)}"
        body = {
            "contract_id": "room16.ba12.live_retrieval_receipt",
            "contract_version": 1,
            "receipt_id": receipt_id,
            "transport": "live_acquisition",
            **values,
        }
        return cls(**body, receipt_sha256=_domain_hash("room16.ba12.live_retrieval_receipt@1", body))

    @model_validator(mode="after")
    def valid_receipt(self) -> "LiveRetrievalReceipt":
        date.fromisoformat(self.request_as_of_date)
        fetched = datetime.fromisoformat(self.fetched_at_utc.replace("Z", "+00:00"))
        available = datetime.fromisoformat(self.available_at_utc.replace("Z", "+00:00"))
        _utc_timestamp(self.fetched_at_utc, "fetched_at_utc")
        _utc_timestamp(self.available_at_utc, "available_at_utc")
        if self.published_at_utc_or_null is not None:
            _utc_timestamp(self.published_at_utc_or_null, "published_at_utc_or_null")
        if self.filing_date_or_null is not None:
            date.fromisoformat(self.filing_date_or_null)
        cutoff = datetime.combine(
            date.fromisoformat(self.request_as_of_date),
            datetime.max.time(),
            tzinfo=timezone.utc,
        )
        published = (
            datetime.fromisoformat(self.published_at_utc_or_null.replace("Z", "+00:00"))
            if self.published_at_utc_or_null
            else None
        )
        if available > cutoff or (published is not None and published > cutoff):
            raise ValueError("live source violates compile as-of cutoff")
        if fetched.tzinfo is None or available.tzinfo is None:
            raise ValueError("live receipt timestamps require timezone")
        if self.variable_cost_incurred:
            if (
                self.variable_cost_amount_or_null is None
                or self.variable_cost_currency_or_null is None
                or not self.paid_provider_approval_bound
            ):
                raise ValueError("paid live retrieval requires amount, currency and approval")
        elif self.variable_cost_amount_or_null is not None or self.variable_cost_currency_or_null is not None:
            raise ValueError("zero-cost live retrieval cannot record a variable amount")
        expected = _domain_hash(
            "room16.ba12.live_retrieval_receipt@1",
            _model_body(self, "receipt_sha256"),
        )
        if self.receipt_sha256 != expected:
            raise ValueError("live retrieval receipt self-hash mismatch")
        return self


class LiveCaptureBinding(StrictModel):
    contract_id: Literal["room16.ba12.live_capture_binding"] = (
        "room16.ba12.live_capture_binding"
    )
    contract_version: Literal[1] = 1
    binding_id: str = Field(pattern=STABLE_ID_PATTERN)
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    acquisition_plan_sha256: str = Field(pattern=SHA256_PATTERN)
    acquisition_id: str = Field(pattern=STABLE_ID_PATTERN)
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    source_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    live_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    capture_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    payload_bytes: int = Field(ge=1)
    ba3_retrieval_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    ba3_source_snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    live_fetched_at_utc: str
    ba3_retrieved_at_utc: str
    binding_sha256: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def create(cls, **values: object) -> "LiveCaptureBinding":
        seed = {
            "acquisition_id": values["acquisition_id"],
            "ba3_source_snapshot_sha256": values["ba3_source_snapshot_sha256"],
            "live_receipt_sha256": values["live_receipt_sha256"],
        }
        body = {
            "binding_id": f"live-binding.{sha256_json(seed)}",
            "contract_id": "room16.ba12.live_capture_binding",
            "contract_version": 1,
            **values,
        }
        return cls(**body, binding_sha256=_domain_hash("room16.ba12.live_capture_binding@1", body))

    @model_validator(mode="after")
    def valid_binding(self) -> "LiveCaptureBinding":
        _utc_timestamp(self.live_fetched_at_utc, "live_fetched_at_utc")
        _utc_timestamp(self.ba3_retrieved_at_utc, "ba3_retrieved_at_utc")
        expected = _domain_hash(
            "room16.ba12.live_capture_binding@1",
            _model_body(self, "binding_sha256"),
        )
        if self.binding_sha256 != expected:
            raise ValueError("live capture binding self-hash mismatch")
        return self


class LiveCaptureDisposition(StrictModel):
    acquisition_id: str = Field(pattern=STABLE_ID_PATTERN)
    required: bool
    terminal_state: Literal[
        "captured_bound", "failed_required", "failed_optional_dispositioned"
    ]
    live_receipt_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    binding_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    failure_code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{2,127}$")

    @model_validator(mode="after")
    def valid_disposition(self) -> "LiveCaptureDisposition":
        if self.terminal_state == "captured_bound":
            if self.live_receipt_sha256 is None or self.binding_sha256 is None or self.failure_code:
                raise ValueError("captured disposition requires receipt and binding only")
        else:
            if self.live_receipt_sha256 or self.binding_sha256 or self.failure_code is None:
                raise ValueError("failed disposition requires only a failure code")
        if self.required and self.terminal_state == "failed_optional_dispositioned":
            raise ValueError("required acquisition cannot use optional failure disposition")
        if not self.required and self.terminal_state == "failed_required":
            raise ValueError("optional acquisition cannot use required failure disposition")
        return self


class LiveCaptureSet(StrictModel):
    contract_id: Literal["room16.ba12.live_capture_set"] = "room16.ba12.live_capture_set"
    contract_version: Literal[1] = 1
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    acquisition_plan_sha256: str = Field(pattern=SHA256_PATTERN)
    expected_acquisition_ids: tuple[str, ...]
    dispositions: tuple[LiveCaptureDisposition, ...]
    fully_closed: Literal[True] = True
    eligible_for_native_compile: bool
    set_sha256: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def create(
        cls,
        *,
        request_sha256: str,
        acquisition_plan_sha256: str,
        expected_acquisition_ids: tuple[str, ...],
        dispositions: tuple[LiveCaptureDisposition, ...],
    ) -> "LiveCaptureSet":
        expected = tuple(sorted(expected_acquisition_ids))
        ordered = tuple(sorted(dispositions, key=lambda item: item.acquisition_id))
        eligible = all(item.terminal_state != "failed_required" for item in ordered)
        body: dict[str, object] = {
            "acquisition_plan_sha256": acquisition_plan_sha256,
            "contract_id": "room16.ba12.live_capture_set",
            "contract_version": 1,
            "dispositions": [item.model_dump(mode="json") for item in ordered],
            "eligible_for_native_compile": eligible,
            "expected_acquisition_ids": list(expected),
            "fully_closed": True,
            "request_sha256": request_sha256,
        }
        return cls(**body, set_sha256=_domain_hash("room16.ba12.live_capture_set@1", body))

    @model_validator(mode="after")
    def valid_set(self) -> "LiveCaptureSet":
        expected = self.expected_acquisition_ids
        actual = tuple(item.acquisition_id for item in self.dispositions)
        if expected != tuple(sorted(set(expected))) or actual != tuple(sorted(set(actual))):
            raise ValueError("capture-set collections must be sorted and unique")
        if expected != actual:
            raise ValueError("capture set does not exactly cover expected acquisitions")
        eligible = all(item.terminal_state != "failed_required" for item in self.dispositions)
        if self.eligible_for_native_compile != eligible:
            raise ValueError("capture-set eligibility is inconsistent")
        expected_hash = _domain_hash(
            "room16.ba12.live_capture_set@1",
            _model_body(self, "set_sha256"),
        )
        if self.set_sha256 != expected_hash:
            raise ValueError("live capture set self-hash mismatch")
        return self
