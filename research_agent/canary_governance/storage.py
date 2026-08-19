"""Content-addressed BA11 registry storage with CAS and atomic head publication."""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import canonical_json, sha256_json

from .contracts import RegistryHead, RegistrySnapshot
from .diagnostics import CanaryGovernanceError


class ContentAddressedRegistryStore:
    """Research-owned storage; Product receives only immutable snapshot mirrors."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = root / "objects" / "sha256"
        self.snapshots = root / "snapshots"
        self.events = root / "ledger" / "events"
        self.receipts = root / "receipts"
        self.head_path = root / "heads" / "current.json"
        self.lock_path = root / "heads" / ".commit.lock"

    @staticmethod
    def product_mirror_layout(product_root: Path) -> dict[str, Path]:
        return {
            "snapshot": product_root / "config" / "canary_registry_mirror" / "snapshot.json",
            "receipt": product_root / "config" / "canary_registry_mirror" / "mirror_receipt.json",
        }

    def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temp.write_text(canonical_json(payload) + "\n", encoding="utf-8")
        os.replace(temp, path)

    def put_immutable(self, payload: dict[str, Any]) -> str:
        digest = sha256_json(payload)
        path = self.objects / f"{digest}.json"
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != payload:
                raise CanaryGovernanceError("BA11_HASH_MISMATCH", digest)
        else:
            self._atomic_write(path, payload)
        return digest

    def read_head(self) -> RegistryHead | None:
        if not self.head_path.exists():
            return None
        return RegistryHead.model_validate_json(self.head_path.read_text(encoding="utf-8"))

    def commit_snapshot(
        self,
        snapshot: RegistrySnapshot,
        *,
        expected_head_sha256: str | None,
        fault: Callable[[str], None] | None = None,
    ) -> RegistryHead:
        fault = fault or (lambda _step: None)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self.read_head()
            current_hash = current.head_sha256 if current else None
            if current_hash != expected_head_sha256:
                raise CanaryGovernanceError("BA11_REGISTRY_CAS_CONFLICT")
            expected_generation = 0 if current is None else current.registry_generation + 1
            if snapshot.registry_generation != expected_generation:
                raise CanaryGovernanceError("BA11_REGISTRY_GENERATION_INVALID")
            expected_previous_snapshot = None if current is None else current.snapshot_sha256
            if snapshot.previous_registry_sha256 != expected_previous_snapshot:
                raise CanaryGovernanceError("BA11_REGISTRY_PREDECESSOR_INVALID")
            fault("before_object_write")
            self.put_immutable(snapshot.model_dump(mode="json"))
            self._atomic_write(
                self.snapshots / f"{snapshot.snapshot_sha256}.json",
                snapshot.model_dump(mode="json"),
            )
            fault("before_pointer_swap")
            head = RegistryHead.create(
                registry_generation=snapshot.registry_generation,
                previous_head_sha256=current_hash,
                snapshot_sha256=snapshot.snapshot_sha256,
                ledger_head_sha256=snapshot.ledger_head_sha256,
            )
            self._atomic_write(self.head_path, head.model_dump(mode="json"))
            fault("after_pointer_swap")
            reread = self.read_head()
            if reread != head:
                raise CanaryGovernanceError("BA11_HASH_MISMATCH", "head_readback")
            return head
