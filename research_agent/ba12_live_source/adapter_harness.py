"""Dependency-injected integration boundary for existing provider adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .live_receipt import ProviderResponse


def normalize_adapter_result(value: object) -> bytes:
    """Encode real adapter return shapes into deterministic captured bytes."""

    if isinstance(value, bytes):
        if not value:
            raise ValueError("adapter returned empty bytes")
        return value
    if isinstance(value, str):
        payload = value.encode("utf-8")
        if not payload:
            raise ValueError("adapter returned empty text")
        return payload
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        value = to_dict(orient="records")
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
        allow_nan=False,
    ).encode("utf-8")
    if payload in {b"", b"null", b"[]", b"{}"}:
        raise ValueError("adapter returned no usable payload")
    return payload


@dataclass(frozen=True)
class ExistingAdapterHarness:
    """Invoke an actual public adapter method and normalize its real result."""

    provider_id: str
    adapter: object
    method_name: str
    source_id: str
    source_type: str
    original_locator: str
    final_locator: str
    raw_status: str
    media_type: str
    fetched_at_utc: str
    available_at_utc: str
    args: tuple[object, ...] = ()
    kwargs: dict[str, object] = field(default_factory=dict)
    published_at_utc_or_null: str | None = None
    filing_date_or_null: str | None = None
    variable_cost_incurred: bool = False
    variable_cost_amount_or_null: str | None = None
    variable_cost_currency_or_null: str | None = None

    def __call__(self) -> ProviderResponse:
        method = getattr(self.adapter, self.method_name)
        if not callable(method) or self.method_name.startswith("_"):
            raise ValueError("adapter harness requires a public callable method")
        result: Any = method(*self.args, **self.kwargs)
        return ProviderResponse(
            provider_id=self.provider_id,
            source_id=self.source_id,
            source_type=self.source_type,
            original_locator=self.original_locator,
            final_locator=self.final_locator,
            status=self.raw_status,
            media_type=self.media_type,
            payload=normalize_adapter_result(result),
            fetched_at_utc=self.fetched_at_utc,
            available_at_utc=self.available_at_utc,
            published_at_utc_or_null=self.published_at_utc_or_null,
            filing_date_or_null=self.filing_date_or_null,
            variable_cost_incurred=self.variable_cost_incurred,
            variable_cost_amount_or_null=self.variable_cost_amount_or_null,
            variable_cost_currency_or_null=self.variable_cost_currency_or_null,
        )
