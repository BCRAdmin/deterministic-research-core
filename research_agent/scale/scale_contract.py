from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from research_agent.capabilities.market_registry import (
    get_jurisdiction_capability,
    get_provider_capability,
)
from research_agent.current.runner import CurrentResearchRequest, run_current_research


CONTRACT_ID = "room16.zero_cost_scale_plan"
CONTRACT_VERSION = 1
STATE_CONTRACT_ID = "room16.zero_cost_scale_state"
MAX_ITEMS = 1_000
DEFAULT_RUNTIME_ROOT = Path(__file__).resolve().parents[2] / ".runtime" / "room16-scale"
_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,23}")


class ScaleContractError(RuntimeError):
    """Raised when scale planning or execution would violate Room16 policy."""


class ScaleItemRequest(BaseModel):
    ticker: str
    jurisdiction: str
    isin: Optional[str] = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        symbol = str(value or "").strip().upper()
        if not _SYMBOL.fullmatch(symbol):
            raise ValueError("ticker is missing or invalid")
        return symbol

    @field_validator("jurisdiction")
    @classmethod
    def normalize_jurisdiction(cls, value: str) -> str:
        code = str(value or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", code):
            raise ValueError("jurisdiction is missing or invalid")
        return code

    @field_validator("isin")
    @classmethod
    def normalize_isin(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        isin = value.strip().upper()
        if len(isin) != 12 or not isin[:2].isalpha() or not isin.isalnum():
            raise ValueError("ISIN is invalid")
        return isin


class ScalePlanRequest(BaseModel):
    as_of_date: str
    items: list[ScaleItemRequest] = Field(min_length=1, max_length=MAX_ITEMS)
    minimum_interval_seconds: float = Field(default=0.25, ge=0.0, le=60.0)
    zero_variable_cost_required: bool = True
    max_parallel_jobs: int = 1

    @field_validator("as_of_date")
    @classmethod
    def normalize_date(cls, value: str) -> str:
        return date.fromisoformat(value).isoformat()

    @model_validator(mode="after")
    def validate_policy(self) -> "ScalePlanRequest":
        if not self.zero_variable_cost_required:
            raise ValueError("zero_variable_cost_required must remain true")
        if self.max_parallel_jobs != 1:
            raise ValueError("max_parallel_jobs must remain 1")
        identities = [(item.jurisdiction, item.ticker, item.isin or "") for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate scale-plan identity")
        return self


def build_scale_plan(request: ScalePlanRequest) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for index, requested in enumerate(request.items, start=1):
        capability = get_jurisdiction_capability(requested.jurisdiction)
        provider_id = capability.get("defaultPriceProviderId")
        status = "ready"
        reason = "supported_zero_cost_path"
        if capability["status"] != "supported":
            status = "blocked"
            reason = str(capability["message"])
            provider_id = None
        elif not provider_id:
            raise ScaleContractError(
                f"supported_jurisdiction_without_default_provider:{requested.jurisdiction}"
            )
        else:
            provider = get_provider_capability(provider_id)
            if provider["variableCost"] != "none" or provider["automaticUse"] not in {
                "allowed",
                "allowed_when_configured",
            }:
                raise ScaleContractError(f"scale_provider_not_zero_cost:{provider_id}")
        items.append(
            {
                "sequence": index,
                "ticker": requested.ticker,
                "jurisdiction": requested.jurisdiction,
                "isin": requested.isin,
                "status": status,
                "priceProviderId": provider_id,
                "reason": reason,
            }
        )
    payload: dict[str, Any] = {
        "contractId": CONTRACT_ID,
        "contractVersion": CONTRACT_VERSION,
        "asOfDate": request.as_of_date,
        "itemCount": len(items),
        "executionPolicy": {
            "mode": "plan_only",
            "confirmationRequired": True,
            "zeroVariableCostRequired": True,
            "maxParallelJobs": 1,
            "minimumIntervalSeconds": request.minimum_interval_seconds,
            "resumeEnabled": True,
            "failureIsolationEnabled": True,
            "modelRunsAllowed": False,
            "paidProvidersAllowed": False,
            "reportPublishingAllowed": False,
            "externalAutomationAllowed": False,
        },
        "items": items,
    }
    payload["planSha256"] = _payload_sha256(payload)
    return payload


def save_scale_plan(
    plan: dict[str, Any],
    *,
    runtime_root: Optional[Path] = None,
) -> Path:
    validated = validate_scale_plan(plan)
    root = (runtime_root or DEFAULT_RUNTIME_ROOT).expanduser().resolve()
    target = root / "plans" / f"{validated['planSha256']}.json"
    _atomic_write_json(target, validated)
    return target


def load_scale_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScaleContractError("scale_plan_unreadable") from exc
    return validate_scale_plan(payload)


def validate_scale_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) != {
        "contractId",
        "contractVersion",
        "asOfDate",
        "itemCount",
        "executionPolicy",
        "items",
        "planSha256",
    }:
        raise ScaleContractError("scale_plan_shape_invalid")
    if plan.get("contractId") != CONTRACT_ID or plan.get("contractVersion") != CONTRACT_VERSION:
        raise ScaleContractError("scale_plan_contract_invalid")
    try:
        date.fromisoformat(str(plan.get("asOfDate") or ""))
    except ValueError as exc:
        raise ScaleContractError("scale_plan_date_invalid") from exc
    items = plan.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise ScaleContractError("scale_plan_item_count_invalid")
    if plan.get("itemCount") != len(items):
        raise ScaleContractError("scale_plan_item_count_invalid")
    policy = plan.get("executionPolicy")
    expected_policy = {
        "mode": "plan_only",
        "confirmationRequired": True,
        "zeroVariableCostRequired": True,
        "maxParallelJobs": 1,
        "resumeEnabled": True,
        "failureIsolationEnabled": True,
        "modelRunsAllowed": False,
        "paidProvidersAllowed": False,
        "reportPublishingAllowed": False,
        "externalAutomationAllowed": False,
    }
    if not isinstance(policy, dict) or any(policy.get(key) != value for key, value in expected_policy.items()):
        raise ScaleContractError("scale_plan_policy_invalid")
    interval = policy.get("minimumIntervalSeconds")
    if not isinstance(interval, (int, float)) or not 0 <= interval <= 60:
        raise ScaleContractError("scale_plan_interval_invalid")
    identities: set[tuple[str, str, str]] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or set(item) != {
            "sequence",
            "ticker",
            "jurisdiction",
            "isin",
            "status",
            "priceProviderId",
            "reason",
        }:
            raise ScaleContractError("scale_plan_item_invalid")
        if item.get("sequence") != index or item.get("status") not in {"ready", "blocked"}:
            raise ScaleContractError("scale_plan_item_invalid")
        validated = ScaleItemRequest.model_validate(item)
        identity = (validated.jurisdiction, validated.ticker, validated.isin or "")
        if identity in identities:
            raise ScaleContractError("scale_plan_identity_duplicate")
        identities.add(identity)
        capability = get_jurisdiction_capability(validated.jurisdiction)
        if item["status"] == "ready":
            provider_id = item.get("priceProviderId")
            provider = get_provider_capability(str(provider_id or ""))
            if capability["status"] != "supported" or provider_id != capability.get(
                "defaultPriceProviderId"
            ):
                raise ScaleContractError("scale_plan_provider_binding_invalid")
            if provider["variableCost"] != "none":
                raise ScaleContractError("scale_plan_paid_provider_forbidden")
        elif capability["status"] == "supported" or item.get("priceProviderId") is not None:
            raise ScaleContractError("scale_plan_blocked_item_invalid")
    if not _is_sha256(plan.get("planSha256")) or plan["planSha256"] != _payload_sha256(plan):
        raise ScaleContractError("scale_plan_hash_invalid")
    return plan


def execute_scale_plan(
    plan: dict[str, Any],
    *,
    confirmation_sha256: str,
    sec_user_agent: str = "",
    runtime_root: Optional[Path] = None,
    research_runner: Callable[..., dict[str, Any]] = run_current_research,
    sleeper: Callable[[float], None] = time.sleep,
    retry_failures: bool = False,
) -> dict[str, Any]:
    validated = validate_scale_plan(plan)
    if confirmation_sha256 != validated["planSha256"]:
        raise ScaleContractError("scale_plan_confirmation_mismatch")
    root = (runtime_root or DEFAULT_RUNTIME_ROOT).expanduser().resolve()
    run_dir = root / validated["planSha256"]
    state_path = run_dir / "state.json"
    state = _load_or_initialize_state(validated, state_path)
    interval = float(validated["executionPolicy"]["minimumIntervalSeconds"])
    attempted_in_call = 0
    for planned, item_state in zip(validated["items"], state["items"]):
        if item_state["status"] == "completed" or item_state["status"] == "blocked":
            continue
        if item_state["status"] == "failed" and not retry_failures:
            continue
        if attempted_in_call and interval:
            sleeper(interval)
        attempted_in_call += 1
        item_state.update({"status": "running", "error": None})
        state["status"] = "running"
        state["updatedAt"] = _utc_now()
        _atomic_write_json(state_path, state)
        try:
            request = CurrentResearchRequest(
                ticker=planned["ticker"],
                as_of_date=validated["asOfDate"],
                jurisdiction=planned["jurisdiction"],
                isin=planned["isin"],
                sec_user_agent=sec_user_agent,
                price_provider=str(planned["priceProviderId"]),
                staging_root=str(run_dir / "current-research"),
                output_root=str(run_dir / "authority-outputs"),
            )
            result = research_runner(request)
            item_state.update(
                {
                    "status": "completed",
                    "authorityBundle": result.get("authority_bundle"),
                    "analysisAllowed": result.get("analysis_allowed"),
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 - scale execution isolates issuer failures.
            item_state.update(
                {
                    "status": "failed",
                    "authorityBundle": None,
                    "analysisAllowed": False,
                    "error": str(exc),
                }
            )
        item_state["finishedAt"] = _utc_now()
        state["updatedAt"] = _utc_now()
        _refresh_state_status(state)
        _atomic_write_json(state_path, state)
    state["updatedAt"] = _utc_now()
    _refresh_state_status(state)
    _atomic_write_json(state_path, state)
    return state


def _load_or_initialize_state(plan: dict[str, Any], state_path: Path) -> dict[str, Any]:
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScaleContractError("scale_state_unreadable") from exc
        if state.get("contractId") != STATE_CONTRACT_ID or state.get("planSha256") != plan[
            "planSha256"
        ]:
            raise ScaleContractError("scale_state_plan_mismatch")
        if not isinstance(state.get("items"), list) or len(state["items"]) != len(plan["items"]):
            raise ScaleContractError("scale_state_shape_invalid")
        for item in state["items"]:
            if item.get("status") == "running":
                item["status"] = "pending"
        return state
    now = _utc_now()
    state = {
        "contractId": STATE_CONTRACT_ID,
        "contractVersion": 1,
        "planSha256": plan["planSha256"],
        "status": "pending",
        "createdAt": now,
        "updatedAt": now,
        "automaticActions": {
            "modelRun": False,
            "reportPublish": False,
            "codexTask": False,
            "gitWrite": False,
        },
        "items": [
            {
                "sequence": item["sequence"],
                "ticker": item["ticker"],
                "jurisdiction": item["jurisdiction"],
                "status": "blocked" if item["status"] == "blocked" else "pending",
                "authorityBundle": None,
                "analysisAllowed": False,
                "error": item["reason"] if item["status"] == "blocked" else None,
                "finishedAt": now if item["status"] == "blocked" else None,
            }
            for item in plan["items"]
        ],
    }
    _refresh_state_status(state)
    _atomic_write_json(state_path, state)
    return state


def _refresh_state_status(state: dict[str, Any]) -> None:
    counts = {name: 0 for name in ("pending", "running", "completed", "failed", "blocked")}
    for item in state["items"]:
        counts[item["status"]] += 1
    state["counts"] = counts
    if counts["pending"] or counts["running"]:
        state["status"] = "running"
    elif counts["failed"]:
        state["status"] = "completed_with_failures"
    elif counts["blocked"]:
        state["status"] = "completed_with_blocks"
    else:
        state["status"] = "completed"


def _payload_sha256(payload: dict[str, Any]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "planSha256"}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
