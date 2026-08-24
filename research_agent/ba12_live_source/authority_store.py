"""Content-addressed durable graph storage for RFC-0010 R2."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from research_agent.compiler_foundation.canonical import canonical_bytes
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR

from .contracts import (
    LiveAttemptRecord,
    LiveCaptureBinding,
    LiveCaptureSet,
    LiveRunClosure,
    fail,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class RecoveredLiveRun:
    closure: LiveRunClosure
    capture_set: LiveCaptureSet
    attempts: tuple[LiveAttemptRecord, ...]
    bindings: tuple[LiveCaptureBinding, ...]
    snapshot: SourceSnapshotIR | None


class LiveAuthorityStore:
    """Persist and reload the final attempt/binding/set/BA3 authority graph."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink():
            raise fail("LIVE_AUTHORITY_ROOT_SYMLINK", "authority root must not be a symlink")
        self.root = root.resolve()

    @staticmethod
    def _persist_once(path: Path, payload: bytes) -> bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.parent.is_symlink():
            raise fail("LIVE_AUTHORITY_PATH_SYMLINK", "authority path is symlinked")
        if path.exists():
            stored = path.read_bytes()
            if stored != payload:
                raise fail("LIVE_AUTHORITY_CONFLICT", "authority path contains different bytes")
            return stored
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".authority-", dir=path.parent, delete=False
            ) as handle:
                temporary_name = handle.name
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, path, follow_symlinks=False)
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise fail("LIVE_AUTHORITY_CONFLICT", "concurrent authority differs")
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
        path.chmod(0o444)
        return path.read_bytes()

    def _persist_model(self, category: str, digest: str, value: BaseModel) -> None:
        self._persist_once(
            self.root / category / f"{digest}.json",
            canonical_bytes(value.model_dump(mode="json")),
        )

    def _load_model(self, category: str, digest: str, model: type[ModelT]) -> ModelT:
        path = self.root / category / f"{digest}.json"
        if path.is_symlink() or not path.is_file():
            raise fail("LIVE_AUTHORITY_OBJECT_MISSING", f"missing {category} authority object")
        try:
            return model.model_validate(json.loads(path.read_bytes()))
        except (json.JSONDecodeError, ValueError) as exc:
            raise fail("LIVE_AUTHORITY_OBJECT_INVALID", f"invalid {category} authority object") from exc

    def persist_closed_graph(
        self,
        *,
        capture_set: LiveCaptureSet,
        attempts: tuple[LiveAttemptRecord, ...],
        bindings: tuple[LiveCaptureBinding, ...] = (),
        snapshot: SourceSnapshotIR | None = None,
    ) -> LiveRunClosure:
        if any(record.terminal_state == "prepared_capture" for record in attempts):
            raise fail("LIVE_RUN_NOT_TERMINAL", "run closure requires terminal attempts")
        expected_ids = capture_set.expected_acquisition_ids
        attempt_ids = tuple(sorted(record.acquisition_id for record in attempts))
        if attempt_ids != expected_ids:
            raise fail("LIVE_RUN_ATTEMPT_COVERAGE", "terminal attempts must exactly cover plan")
        eligible = capture_set.eligible_for_native_compile
        if eligible != (snapshot is not None):
            raise fail("LIVE_RUN_GRAPH_ELIGIBILITY", "BA3 snapshot presence differs from eligibility")
        if eligible and len(bindings) != len(expected_ids):
            raise fail("LIVE_RUN_BINDING_COVERAGE", "eligible run requires every binding")
        if not eligible and bindings:
            raise fail("LIVE_RUN_INELIGIBLE_BINDING", "ineligible run cannot claim BA3 bindings")

        self._persist_model("capture_sets", capture_set.set_sha256, capture_set)
        for binding in bindings:
            self._persist_model("bindings", binding.binding_sha256, binding)
        if snapshot is not None:
            self._persist_model("snapshots", snapshot.snapshot_sha256, snapshot)
        for attempt in attempts:
            self._persist_model("attempt_records", attempt.record_sha256, attempt)

        closure = LiveRunClosure.create(
            request_sha256=capture_set.request_sha256,
            acquisition_plan_sha256=capture_set.acquisition_plan_sha256,
            expected_acquisition_ids=expected_ids,
            attempt_record_sha256s=tuple(sorted(item.record_sha256 for item in attempts)),
            binding_sha256s=tuple(sorted(item.binding_sha256 for item in bindings)),
            capture_set_sha256=capture_set.set_sha256,
            ba3_source_snapshot_sha256_or_null=(snapshot.snapshot_sha256 if snapshot else None),
            eligible_for_native_compile=eligible,
        )
        self._persist_model("run_closures", closure.closure_sha256, closure)
        return closure

    def load_closed_run(self, closure_sha256: str) -> RecoveredLiveRun:
        closure = self._load_model("run_closures", closure_sha256, LiveRunClosure)
        if closure.closure_sha256 != closure_sha256:
            raise fail("LIVE_RUN_CLOSURE_HASH_MISMATCH", "closure filename and self-hash differ")
        capture_set = self._load_model(
            "capture_sets", closure.capture_set_sha256, LiveCaptureSet
        )
        if capture_set.set_sha256 != closure.capture_set_sha256:
            raise fail("LIVE_RUN_SET_HASH_MISMATCH", "capture set hash link differs")
        attempts = tuple(
            self._load_model("attempt_records", digest, LiveAttemptRecord)
            for digest in closure.attempt_record_sha256s
        )
        bindings = tuple(
            self._load_model("bindings", digest, LiveCaptureBinding)
            for digest in closure.binding_sha256s
        )
        snapshot = (
            self._load_model(
                "snapshots",
                closure.ba3_source_snapshot_sha256_or_null,
                SourceSnapshotIR,
            )
            if closure.ba3_source_snapshot_sha256_or_null
            else None
        )
        if (
            capture_set.request_sha256 != closure.request_sha256
            or capture_set.acquisition_plan_sha256 != closure.acquisition_plan_sha256
            or capture_set.expected_acquisition_ids != closure.expected_acquisition_ids
            or capture_set.eligible_for_native_compile != closure.eligible_for_native_compile
            or tuple(sorted(item.record_sha256 for item in attempts))
            != closure.attempt_record_sha256s
            or tuple(sorted(item.binding_sha256 for item in bindings))
            != closure.binding_sha256s
            or (snapshot.snapshot_sha256 if snapshot else None)
            != closure.ba3_source_snapshot_sha256_or_null
        ):
            raise fail("LIVE_RUN_GRAPH_MISMATCH", "loaded run graph hash links differ")
        return RecoveredLiveRun(
            closure=closure,
            capture_set=capture_set,
            attempts=attempts,
            bindings=bindings,
            snapshot=snapshot,
        )
