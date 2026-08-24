"""Immutable, content-addressed byte storage for RFC-0010 Stage A."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from research_agent.compiler_foundation.canonical import canonical_bytes

from .contracts import LiveCaptureArtifact, fail


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class ContentAddressedCaptureStore:
    """Persist live response bytes before any parser or semantic consumer sees them."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink():
            raise fail("LIVE_CAPTURE_ROOT_SYMLINK", "capture root must not be a symlink")
        self.root = root.resolve()

    def _target(self, content_sha256: str) -> tuple[str, Path]:
        relative = f"captures/sha256/{content_sha256[:2]}/{content_sha256}"
        target = self.root / relative
        resolved_parent = target.parent.resolve()
        try:
            resolved_parent.relative_to(self.root)
        except ValueError as exc:
            raise fail("LIVE_CAPTURE_PATH_ESCAPE", "capture path escapes the store") from exc
        return relative, target

    @staticmethod
    def _readback(path: Path) -> tuple[str, int]:
        if path.is_symlink() or not path.is_file():
            raise fail("LIVE_CAPTURE_PATH_UNSAFE", "capture object is missing or symlinked")
        payload = path.read_bytes()
        return sha256_bytes(payload), len(payload)

    @staticmethod
    def _persist_once(path: Path, payload: bytes) -> bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.parent.is_symlink():
            raise fail("LIVE_CAPTURE_PATH_SYMLINK", "capture metadata path is symlinked")
        if path.exists():
            return path.read_bytes()
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".metadata-", dir=path.parent, delete=False
            ) as handle:
                temporary_name = handle.name
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, path, follow_symlinks=False)
            except FileExistsError:
                pass
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
        path.chmod(0o444)
        return path.read_bytes()

    def persist(
        self,
        payload: bytes,
        *,
        media_type: str,
        write_completed_at_utc: str,
    ) -> LiveCaptureArtifact:
        if not isinstance(payload, bytes) or not payload:
            raise fail("LIVE_CAPTURE_EMPTY", "live response must contain bytes")
        content_sha256 = sha256_bytes(payload)
        relative, target = self._target(content_sha256)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.parent.is_symlink():
            raise fail("LIVE_CAPTURE_PATH_SYMLINK", "capture hash directory is symlinked")

        if target.exists() or target.is_symlink():
            readback_sha256, readback_bytes = self._readback(target)
            if readback_sha256 != content_sha256 or readback_bytes != len(payload):
                raise fail(
                    "LIVE_CAPTURE_IMMUTABLE_CONFLICT",
                    "existing content-addressed object differs from requested bytes",
                )
        else:
            temporary_name: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb", prefix=".capture-", dir=target.parent, delete=False
                ) as handle:
                    temporary_name = handle.name
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(temporary_name, target, follow_symlinks=False)
                except FileExistsError:
                    # An identical concurrent writer may have won the link race.
                    pass
                directory_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temporary_name is not None:
                    Path(temporary_name).unlink(missing_ok=True)

        readback_sha256, readback_bytes = self._readback(target)
        if readback_sha256 != content_sha256 or readback_bytes != len(payload):
            raise fail("LIVE_CAPTURE_READBACK_MISMATCH", "capture readback verification failed")
        target.chmod(0o444)
        candidate = LiveCaptureArtifact.create(
            content_sha256=content_sha256,
            byte_length=len(payload),
            media_type=media_type,
            content_addressed_relative_path=relative,
            write_completed_at_utc=write_completed_at_utc,
            readback_sha256=readback_sha256,
            readback_byte_length=readback_bytes,
        )
        metadata_path = self.root / "metadata" / f"{content_sha256}.json"
        stored = self._persist_once(
            metadata_path,
            canonical_bytes(candidate.model_dump(mode="json")),
        )
        try:
            artifact = LiveCaptureArtifact.model_validate(json.loads(stored))
        except (json.JSONDecodeError, ValueError) as exc:
            raise fail("LIVE_CAPTURE_METADATA_INVALID", "capture metadata is invalid") from exc
        if (
            artifact.content_sha256 != content_sha256
            or artifact.byte_length != len(payload)
            or artifact.media_type != media_type
        ):
            raise fail(
                "LIVE_CAPTURE_METADATA_CONFLICT",
                "existing capture metadata conflicts with the content object",
            )
        return artifact

    def read_verified(self, artifact: LiveCaptureArtifact) -> bytes:
        expected_relative = (
            f"captures/sha256/{artifact.content_sha256[:2]}/{artifact.content_sha256}"
        )
        if artifact.content_addressed_relative_path != expected_relative:
            raise fail("LIVE_CAPTURE_PATH_MISMATCH", "artifact path is not content-addressed")
        target = self.root / artifact.content_addressed_relative_path
        if target.is_symlink():
            raise fail("LIVE_CAPTURE_PATH_SYMLINK", "capture object is symlinked")
        try:
            target.resolve().relative_to(self.root)
        except ValueError as exc:
            raise fail("LIVE_CAPTURE_PATH_ESCAPE", "capture object escapes the store") from exc
        payload = target.read_bytes() if target.is_file() else b""
        if len(payload) != artifact.byte_length or sha256_bytes(payload) != artifact.content_sha256:
            raise fail("LIVE_CAPTURE_READBACK_MISMATCH", "capture object failed verification")
        return payload
