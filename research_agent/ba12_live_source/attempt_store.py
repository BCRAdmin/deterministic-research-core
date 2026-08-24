"""Durable append-only attempt authority for RFC-0010 R2."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from research_agent.compiler_foundation.canonical import canonical_bytes

from .capture_store import sha256_bytes
from .contracts import LiveAttemptRecord, fail


def attempt_identity(request_sha256: str, acquisition_id: str, attempt_id: str) -> str:
    return sha256_bytes(
        f"{request_sha256}\0{acquisition_id}\0{attempt_id}".encode("utf-8")
    )


class LiveAttemptStore:
    """Persist prepared and terminal records using immutable CAS-safe files."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink():
            raise fail("LIVE_ATTEMPT_ROOT_SYMLINK", "attempt root must not be a symlink")
        self.root = root.resolve()

    def _directory(self, record: LiveAttemptRecord) -> Path:
        return self.root / attempt_identity(
            record.request_sha256,
            record.acquisition_id,
            record.attempt_id,
        )

    @staticmethod
    def _persist_once(path: Path, payload: bytes) -> bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.parent.is_symlink():
            raise fail("LIVE_ATTEMPT_PATH_SYMLINK", "attempt authority path is symlinked")
        if path.exists():
            stored = path.read_bytes()
            if stored != payload:
                raise fail(
                    "LIVE_DUPLICATE_ATTEMPT_CONFLICT",
                    "attempt identity already has conflicting durable authority",
                )
            return stored
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".attempt-", dir=path.parent, delete=False
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
                        "concurrent attempt produced conflicting durable authority",
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
        return path.read_bytes()

    def persist(self, record: LiveAttemptRecord) -> LiveAttemptRecord:
        filename = "prepared.json" if record.terminal_state == "prepared_capture" else "terminal.json"
        directory = self._directory(record)
        other_path = directory / (
            "terminal.json" if record.terminal_state == "prepared_capture" else "prepared.json"
        )
        if other_path.is_file():
            try:
                other = LiveAttemptRecord.model_validate(json.loads(other_path.read_bytes()))
            except (json.JSONDecodeError, ValueError) as exc:
                raise fail("LIVE_ATTEMPT_RECORD_INVALID", "paired attempt record is invalid") from exc
            if (
                record.terminal_state == "failed"
                or other.terminal_state == "failed"
                or record.request_sha256 != other.request_sha256
                or record.acquisition_plan_sha256 != other.acquisition_plan_sha256
                or record.acquisition_id != other.acquisition_id
                or record.attempt_id != other.attempt_id
                or record.provider_id != other.provider_id
                or record.adapter_id != other.adapter_id
                or record.source_id_or_null != other.source_id_or_null
                or record.source_type_or_null != other.source_type_or_null
                or record.original_locator_or_null != other.original_locator_or_null
                or record.final_locator_or_null != other.final_locator_or_null
                or record.raw_status_or_null != other.raw_status_or_null
                or record.payload_sha256_or_null != other.payload_sha256_or_null
                or record.payload_bytes_or_null != other.payload_bytes_or_null
            ):
                raise fail(
                    "LIVE_DUPLICATE_ATTEMPT_CONFLICT",
                    "prepared and terminal attempt authority conflict",
                )
        stored = self._persist_once(
            directory / filename,
            canonical_bytes(record.model_dump(mode="json")),
        )
        try:
            loaded = LiveAttemptRecord.model_validate(json.loads(stored))
        except (json.JSONDecodeError, ValueError) as exc:
            raise fail("LIVE_ATTEMPT_RECORD_INVALID", "stored attempt record is invalid") from exc
        if loaded.record_sha256 != record.record_sha256:
            raise fail("LIVE_ATTEMPT_RECORD_CONFLICT", "stored attempt record differs")
        return loaded

    def load(
        self,
        *,
        request_sha256: str,
        acquisition_id: str,
        attempt_id: str,
        terminal_only: bool = False,
    ) -> LiveAttemptRecord:
        directory = self.root / attempt_identity(request_sha256, acquisition_id, attempt_id)
        terminal = directory / "terminal.json"
        prepared = directory / "prepared.json"
        path = terminal if terminal.is_file() else prepared
        if terminal_only and path != terminal:
            raise fail("LIVE_ATTEMPT_NOT_TERMINAL", "attempt has no terminal record")
        if path.is_symlink() or not path.is_file():
            raise fail("LIVE_ATTEMPT_NOT_FOUND", "durable attempt record is missing")
        try:
            record = LiveAttemptRecord.model_validate(json.loads(path.read_bytes()))
        except (json.JSONDecodeError, ValueError) as exc:
            raise fail("LIVE_ATTEMPT_RECORD_INVALID", "attempt record failed verification") from exc
        if (
            record.request_sha256 != request_sha256
            or record.acquisition_id != acquisition_id
            or record.attempt_id != attempt_id
        ):
            raise fail("LIVE_ATTEMPT_IDENTITY_MISMATCH", "attempt path and record differ")
        return record

    def terminal_for_run(
        self,
        *,
        request_sha256: str,
        acquisition_plan_sha256: str,
    ) -> tuple[LiveAttemptRecord, ...]:
        records: list[LiveAttemptRecord] = []
        for path in sorted(self.root.glob("*/terminal.json")):
            if path.is_symlink():
                raise fail("LIVE_ATTEMPT_PATH_SYMLINK", "attempt record is symlinked")
            try:
                record = LiveAttemptRecord.model_validate(json.loads(path.read_bytes()))
            except (json.JSONDecodeError, ValueError) as exc:
                raise fail("LIVE_ATTEMPT_RECORD_INVALID", "attempt record failed verification") from exc
            if (
                record.request_sha256 == request_sha256
                and record.acquisition_plan_sha256 == acquisition_plan_sha256
            ):
                records.append(record)
        return tuple(sorted(records, key=lambda item: (item.acquisition_id, item.attempt_id)))
