"""Append-only, hash-chained RFC-0011 operational evidence ledger."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import canonical_json, sha256_json
from research_agent.compiler_foundation.contracts import StrictModel


class OperationsLedgerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class OperationsRunHeader(StrictModel):
    contract_id: str = "room16.alpha.operations_run_header"
    contract_version: int = 1
    run_id: str
    ticker: str
    archetype: str
    as_of_date: str
    research_commit: str
    research_tree: str
    product_commit: str
    product_tree: str
    source_policy_sha: str
    resolver_profile_sha: str
    period_policy_sha: str
    start_time: str
    end_time: str | None = None
    final_status: Literal["RUNNING", "PASS", "FAILED", "BLOCKED"] = "RUNNING"
    manual_intervention_count: int = Field(default=0, ge=0)


class OperationsEvent(StrictModel):
    contract_id: str = "room16.alpha.operations_stage_event"
    contract_version: int = 1
    event_id: str
    run_id: str
    sequence: int = Field(ge=1)
    stage: str
    attempt: int = Field(ge=1)
    started_at: str
    ended_at: str
    duration_ms: int = Field(ge=0)
    status: Literal["STARTED", "PASS", "FAILED", "RECOVERED", "BLOCKED"]
    provider_id_or_null: str | None = None
    provider_status_or_null: str | None = None
    network_call_count: int = Field(ge=0)
    capture_bytes: int = Field(ge=0)
    input_sha256s: tuple[str, ...]
    output_sha256s: tuple[str, ...]
    diagnostic_codes: tuple[str, ...]
    unsupported_metric_count: int = Field(default=0, ge=0)
    stale_metric_count: int = Field(default=0, ge=0)
    core_metric_coverage: int = Field(default=0, ge=0)
    report_section_completeness: int = Field(default=0, ge=0)
    manual_semantic_intervention_count: int = Field(default=0, ge=0)
    previous_event_sha256: str | None
    event_sha256: str

    @classmethod
    def create(cls, **values: object) -> "OperationsEvent":
        seed = {
            "run_id": values["run_id"],
            "sequence": values["sequence"],
            "stage": values["stage"],
            "attempt": values["attempt"],
            "previous_event_sha256": values.get("previous_event_sha256"),
        }
        body = {
            "contract_id": "room16.alpha.operations_stage_event",
            "contract_version": 1,
            "event_id": f"ops-event.{sha256_json(seed)}",
            "provider_id_or_null": None,
            "provider_status_or_null": None,
            "unsupported_metric_count": 0,
            "stale_metric_count": 0,
            "core_metric_coverage": 0,
            "report_section_completeness": 0,
            "manual_semantic_intervention_count": 0,
            **values,
        }
        return cls(**body, event_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_self_hash(self) -> "OperationsEvent":
        value = self.model_dump(mode="json")
        value.pop("event_sha256")
        if sha256_json(value) != self.event_sha256:
            raise ValueError("operations event self-hash mismatch")
        return self


class OperationsLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = path.with_suffix(path.suffix + ".lock")

    def _read_unlocked(self) -> tuple[OperationsEvent, ...]:
        if not self.path.exists():
            return ()
        events: list[OperationsEvent] = []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(OperationsEvent.model_validate(json.loads(line)))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise OperationsLedgerError("OPS_LEDGER_INVALID", str(exc)) from exc
        self._verify_events(tuple(events))
        return tuple(events)

    @staticmethod
    def _verify_events(events: tuple[OperationsEvent, ...]) -> None:
        previous: str | None = None
        seen: set[str] = set()
        for expected_sequence, event in enumerate(events, start=1):
            if event.sequence != expected_sequence:
                raise OperationsLedgerError("OPS_SEQUENCE_INVALID", str(event.sequence))
            if event.previous_event_sha256 != previous:
                raise OperationsLedgerError("OPS_CHAIN_INVALID", event.event_id)
            if event.event_id in seen:
                raise OperationsLedgerError("OPS_DUPLICATE_EVENT", event.event_id)
            seen.add(event.event_id)
            previous = event.event_sha256

    def verify(self) -> tuple[OperationsEvent, ...]:
        return self._read_unlocked()

    def append(self, **values: object) -> OperationsEvent:
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            events = self._read_unlocked()
            expected = len(events) + 1
            supplied = int(values.get("sequence", expected))
            if supplied != expected:
                raise OperationsLedgerError("OPS_SEQUENCE_INVALID", f"expected {expected}, got {supplied}")
            previous = events[-1].event_sha256 if events else None
            supplied_previous = values.get("previous_event_sha256", previous)
            if supplied_previous != previous:
                raise OperationsLedgerError("OPS_CHAIN_INVALID", "previous hash differs")
            event = OperationsEvent.create(
                **{**values, "sequence": expected, "previous_event_sha256": previous}
            )
            if any(existing.event_id == event.event_id for existing in events):
                raise OperationsLedgerError("OPS_DUPLICATE_EVENT", event.event_id)
            descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
            try:
                os.write(descriptor, (canonical_json(event.model_dump(mode="json")) + "\n").encode())
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return event

    def aggregate(self) -> dict[str, object]:
        events = self.verify()
        run_ids = sorted({item.run_id for item in events})
        terminal = {"PASS", "FAILED", "BLOCKED"}
        last_by_run = {run_id: [item for item in events if item.run_id == run_id][-1] for run_id in run_ids}
        return {
            "contract_id": "room16.alpha.operations_aggregate",
            "contract_version": 1,
            "completed_runs": sum(item.status == "PASS" for item in last_by_run.values()),
            "failed_runs": sum(item.status in {"FAILED", "BLOCKED"} for item in last_by_run.values()),
            "incomplete_runs": sum(item.status not in terminal for item in last_by_run.values()),
            "provider_failures": sum(item.provider_id_or_null is not None and item.status == "FAILED" for item in events),
            "manual_interventions": sum(item.manual_semantic_intervention_count for item in events),
            "replay_provider_calls": sum(item.network_call_count for item in events if item.stage == "offline_replay"),
            "unsupported_metric_count": sum(item.unsupported_metric_count for item in events),
            "stale_metric_count": sum(item.stale_metric_count for item in events),
            "core_metric_coverage": sum(item.core_metric_coverage for item in events),
            "report_section_completeness": sum(item.report_section_completeness for item in events),
            "event_count": len(events),
            "chain_tip_sha256": events[-1].event_sha256 if events else None,
        }


def verify_batch_gate(aggregate: dict[str, object]) -> None:
    if int(aggregate.get("replay_provider_calls", 0)) > 0:
        raise OperationsLedgerError("OPS_REPLAY_NETWORK_CALLS", "offline replay called a provider")
    if int(aggregate.get("manual_interventions", 0)) > 0:
        raise OperationsLedgerError("OPS_MANUAL_SEMANTIC_INTERVENTION", "manual semantic intervention")
