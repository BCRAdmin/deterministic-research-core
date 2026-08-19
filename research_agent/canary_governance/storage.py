"""Research-owned append-only ledgers and atomic governance transactions."""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import canonical_json, sha256_json

from .approval import TrustedRoleKeyPolicy, verify_approval, verify_independent_review
from .contracts import (
    AcceptedDebtEvent,
    ArchiveReceipt,
    CanaryFreezeRecord,
    ComparisonResult,
    DebtLedgerHead,
    GenesisImportHead,
    GenesisImportReceipt,
    IndependentReviewAttestation,
    OperatorApprovalReceipt,
    RegistryCommitReceipt,
    RegistryEvent,
    RegistryHead,
    RegistryLedgerHead,
    RegistryPreparedReceipt,
    RegistrySnapshot,
    RegistryTransaction,
    PromotionEvent,
    RejectionEvent,
    RecoveryEvent,
    StaleEvent,
    SupersessionEvent,
    domain_hash,
)
from .diagnostics import CanaryGovernanceError
from .ledger import (
    build_debt_ledger_head,
    build_registry_ledger_head,
    verify_debt_ledger,
    verify_derived_snapshot,
)


class ContentAddressedRegistryStore:
    """Single-writer publication rail; Product receives immutable mirrors only."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = root / "objects" / "sha256"
        self.snapshots = root / "snapshots"
        self.transactions = root / "transactions"
        self.receipts = root / "receipts"
        self.registry_events = root / "ledger" / "registry" / "events"
        self.registry_ledger_head_path = root / "ledger" / "registry" / "head.json"
        self.debt_events = root / "ledger" / "debt" / "events"
        self.debt_ledger_head_path = root / "ledger" / "debt" / "head.json"
        self.genesis_head_path = root / "genesis" / "head.json"
        self.head_path = root / "heads" / "current.json"
        self.lock_path = root / "heads" / ".commit.lock"

    @staticmethod
    def product_mirror_layout(product_root: Path) -> dict[str, Path]:
        return {
            "snapshot": product_root / "config" / "canary_registry_mirror" / "snapshot.json",
            "authority_receipt": product_root
            / "config"
            / "canary_registry_mirror"
            / "research_authority_receipt.json",
            "receipt": product_root / "config" / "canary_registry_mirror" / "mirror_receipt.json",
        }

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(canonical_json(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        self._fsync_directory(path.parent)

    def put_immutable(self, payload: dict[str, Any]) -> str:
        digest = sha256_json(payload)
        path = self.objects / f"{digest}.json"
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != payload:
                raise CanaryGovernanceError("BA11_HASH_MISMATCH", digest)
        else:
            self._atomic_write(path, payload)
        return digest

    @staticmethod
    def _read_model(path: Path, model_type):
        if not path.exists():
            return None
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))

    def read_head(self) -> RegistryHead | None:
        return self._read_model(self.head_path, RegistryHead)

    def read_registry_ledger_head(self) -> RegistryLedgerHead | None:
        return self._read_model(self.registry_ledger_head_path, RegistryLedgerHead)

    def read_debt_ledger_head(self) -> DebtLedgerHead | None:
        return self._read_model(self.debt_ledger_head_path, DebtLedgerHead)

    def _read_events(self, root: Path, model_type) -> tuple:
        if not root.exists():
            return ()
        records = []
        registry_models = {
            "room16.canary_promotion_event": PromotionEvent,
            "room16.canary_rejection_event": RejectionEvent,
            "room16.canary_recovery_event": RecoveryEvent,
            "room16.canary_stale_event": StaleEvent,
            "room16.canary_supersession_event": SupersessionEvent,
        }
        for path in sorted(root.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            selected = registry_models.get(raw.get("contract_id"), model_type)
            records.append(selected.model_validate(raw))
        return tuple(records)

    def append_registry_event(
        self,
        event: RegistryEvent,
        *,
        expected_head_sha256: str | None,
    ) -> RegistryLedgerHead:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self.read_registry_ledger_head()
            current_hash = current.head_sha256 if current else None
            if current_hash != expected_head_sha256:
                raise CanaryGovernanceError("BA11_LEDGER_FORK", "registry")
            events = self._read_events(self.registry_events, RegistryEvent)
            if event.sequence != len(events):
                raise CanaryGovernanceError("BA11_EVENT_CHAIN_BROKEN", "registry_sequence")
            expected_previous = events[-1].event_sha256 if events else None
            if event.previous_event_sha256 != expected_previous:
                raise CanaryGovernanceError("BA11_LEDGER_FORK", "registry_previous")
            self.put_immutable(event.model_dump(mode="json"))
            self._atomic_write(
                self.registry_events / f"{event.sequence:020d}-{event.event_sha256}.json",
                event.model_dump(mode="json"),
            )
            head = build_registry_ledger_head(
                (*events, event),
                generation=0 if current is None else current.generation + 1,
                previous_head_sha256=current_hash,
            )
            self._atomic_write(self.registry_ledger_head_path, head.model_dump(mode="json"))
            return head

    def append_debt_event(
        self,
        event: AcceptedDebtEvent,
        *,
        expected_head_sha256: str | None,
    ) -> DebtLedgerHead:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self.read_debt_ledger_head()
            current_hash = current.head_sha256 if current else None
            if current_hash != expected_head_sha256:
                raise CanaryGovernanceError("BA11_LEDGER_FORK", "debt")
            events = self._read_events(self.debt_events, AcceptedDebtEvent)
            if event.sequence != len(events):
                raise CanaryGovernanceError("BA11_DEBT_CHAIN_BROKEN", "sequence")
            expected_previous = events[-1].event_sha256 if events else None
            if event.previous_event_sha256 != expected_previous:
                raise CanaryGovernanceError("BA11_LEDGER_FORK", "debt_previous")
            self.put_immutable(event.model_dump(mode="json"))
            self._atomic_write(
                self.debt_events / f"{event.sequence:020d}-{event.event_sha256}.json",
                event.model_dump(mode="json"),
            )
            head = build_debt_ledger_head(
                (*events, event),
                generation=0 if current is None else current.generation + 1,
                previous_head_sha256=current_hash,
            )
            self._atomic_write(self.debt_ledger_head_path, head.model_dump(mode="json"))
            return head

    def commit_genesis_import(self, receipt: GenesisImportReceipt) -> GenesisImportHead:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if self.genesis_head_path.exists():
                raise CanaryGovernanceError("BA11_GENESIS_ALREADY_IMPORTED")
            self.put_immutable(receipt.model_dump(mode="json"))
            head = GenesisImportHead.create(import_receipt_sha256=receipt.receipt_sha256)
            self._atomic_write(self.genesis_head_path, head.model_dump(mode="json"))
            return head

    def _current_replay_state(self, current: RegistryHead | None) -> tuple[set[str], int, int]:
        if current is None:
            return set(), 0, 0
        path = self.transactions / f"{current.transaction_sha256}.json"
        if not path.exists():
            raise CanaryGovernanceError("BA11_TRANSACTION_RECOVERY_INVALID", "missing_current_transaction")
        transaction = RegistryTransaction.model_validate_json(path.read_text(encoding="utf-8"))
        return set(transaction.consumed_nonces), current.operator_counter, current.reviewer_counter

    @staticmethod
    def _event_set_sha256(events: Iterable[RegistryEvent]) -> str:
        return domain_hash(
            "room16.canary_registry_event_set@1",
            [event.model_dump(mode="json") for event in events],
        )

    def commit_transaction(
        self,
        transaction: RegistryTransaction,
        *,
        snapshot: RegistrySnapshot,
        registry_events: tuple[RegistryEvent, ...],
        registry_ledger_head: RegistryLedgerHead,
        debt_events: tuple[AcceptedDebtEvent, ...],
        debt_ledger_head: DebtLedgerHead,
        freeze: CanaryFreezeRecord,
        comparison_result: ComparisonResult,
        independent_review: IndependentReviewAttestation,
        operator_approval: OperatorApprovalReceipt,
        archive_receipt: ArchiveReceipt,
        artifact_set_sha256: str,
        trusted_role_key_policy: TrustedRoleKeyPolicy,
        revoked_key_ids: set[str],
        expected_subject_ids: tuple[str, ...],
        expected_subject_sha256s: tuple[str, ...],
        expected_finding_set_sha256: str,
        fixed_now_utc: str,
        fault: Callable[[str], None] | None = None,
    ) -> tuple[RegistryHead, RegistryCommitReceipt]:
        fault = fault or (lambda _step: None)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self.read_head()
            if current and current.transaction_sha256 == transaction.transaction_sha256:
                receipt = RegistryCommitReceipt.create(
                    transaction_sha256=transaction.transaction_sha256,
                    published_head_sha256=current.head_sha256,
                    commit_state="recovered",
                    committed_at_utc=fixed_now_utc,
                )
                self._atomic_write(
                    self.receipts / f"{receipt.receipt_sha256}.json", receipt.model_dump(mode="json")
                )
                return current, receipt

            current_hash = current.head_sha256 if current else None
            if current_hash != transaction.base_head_sha256:
                raise CanaryGovernanceError("BA11_REGISTRY_CAS_CONFLICT")
            expected_generation = 0 if current is None else current.registry_generation + 1
            if transaction.registry_generation != expected_generation:
                raise CanaryGovernanceError("BA11_REGISTRY_GENERATION_INVALID")
            previous_snapshot = None if current is None else current.snapshot_sha256
            if snapshot.previous_registry_sha256 != previous_snapshot:
                raise CanaryGovernanceError("BA11_REGISTRY_PREDECESSOR_INVALID")

            verify_derived_snapshot(snapshot, registry_events, expected_head=registry_ledger_head)
            verify_debt_ledger(
                debt_events,
                expected_head=debt_ledger_head,
                authentic_approval_sha256s={operator_approval.approval_sha256},
            )
            consumed_nonces, operator_counter, reviewer_counter = self._current_replay_state(current)
            previous_authority = current_hash or "0" * 64
            verify_independent_review(
                independent_review,
                trusted_role_key_policy=trusted_role_key_policy,
                revoked_key_ids=revoked_key_ids,
                consumed_nonces=consumed_nonces,
                minimum_monotonic_counter=reviewer_counter,
                expected_decision="accepted",
                expected_scope="ba11_canary_promotion",
                expected_subject_ids=expected_subject_ids,
                expected_subject_sha256s=expected_subject_sha256s,
                expected_finding_set_sha256=expected_finding_set_sha256,
                expected_previous_registry_head_sha256=previous_authority,
                fixed_now_utc=fixed_now_utc,
            )
            verify_approval(
                operator_approval,
                trusted_role_key_policy=trusted_role_key_policy,
                revoked_key_ids=revoked_key_ids,
                consumed_nonces=consumed_nonces,
                minimum_monotonic_counter=operator_counter,
                expected_decision="approve",
                expected_scope="ba11_canary_promotion",
                expected_subject_ids=expected_subject_ids,
                expected_subject_sha256s=expected_subject_sha256s,
                expected_finding_set_sha256=expected_finding_set_sha256,
                expected_previous_registry_head_sha256=previous_authority,
                fixed_now_utc=fixed_now_utc,
            )

            expected_nonces = tuple(
                sorted(consumed_nonces | {operator_approval.nonce, independent_review.nonce})
            )
            bindings = {
                "candidate_snapshot_sha256": snapshot.snapshot_sha256,
                "registry_event_set_sha256": self._event_set_sha256(registry_events),
                "registry_ledger_head_sha256": registry_ledger_head.head_sha256,
                "freeze_sha256": freeze.freeze_sha256,
                "comparison_result_sha256": comparison_result.result_sha256,
                "independent_review_sha256": independent_review.attestation_sha256,
                "operator_approval_sha256": operator_approval.approval_sha256,
                "debt_ledger_head_sha256": debt_ledger_head.head_sha256,
                "archive_receipt_sha256": archive_receipt.receipt_sha256,
                "artifact_set_sha256": artifact_set_sha256,
                "consumed_nonces": expected_nonces,
                "operator_counter": operator_approval.monotonic_counter,
                "reviewer_counter": independent_review.monotonic_counter,
            }
            for field, expected in bindings.items():
                if getattr(transaction, field) != expected:
                    raise CanaryGovernanceError("BA11_TRANSACTION_BINDING_INVALID", field)

            fault("before_immutable_staging")
            for model in (
                snapshot, registry_ledger_head, debt_ledger_head, freeze, comparison_result,
                independent_review, operator_approval, archive_receipt, transaction,
            ):
                self.put_immutable(model.model_dump(mode="json"))
            self._atomic_write(
                self.snapshots / f"{snapshot.snapshot_sha256}.json", snapshot.model_dump(mode="json")
            )
            self._atomic_write(
                self.transactions / f"{transaction.transaction_sha256}.json",
                transaction.model_dump(mode="json"),
            )
            fault("after_immutable_staging")
            prepared = RegistryPreparedReceipt.create(
                transaction_sha256=transaction.transaction_sha256,
                expected_base_head_sha256=current_hash,
                prepared_at_utc=fixed_now_utc,
            )
            self._atomic_write(
                self.receipts / f"{prepared.receipt_sha256}.json", prepared.model_dump(mode="json")
            )
            fault("after_prepared_receipt")
            head = RegistryHead.create(
                registry_generation=transaction.registry_generation,
                previous_head_sha256=current_hash,
                snapshot_sha256=snapshot.snapshot_sha256,
                registry_ledger_head_sha256=registry_ledger_head.head_sha256,
                debt_ledger_head_sha256=debt_ledger_head.head_sha256,
                transaction_sha256=transaction.transaction_sha256,
                consumed_nonce_set_sha256=domain_hash("room16.canary_nonce_set@1", expected_nonces),
                operator_counter=operator_approval.monotonic_counter,
                reviewer_counter=independent_review.monotonic_counter,
            )
            fault("before_head_swap")
            self._atomic_write(self.head_path, head.model_dump(mode="json"))
            fault("after_head_swap")
            reread = self.read_head()
            if reread != head:
                raise CanaryGovernanceError("BA11_TRANSACTION_RECOVERY_INVALID", "head_readback")
            fault("after_readback")
            receipt = RegistryCommitReceipt.create(
                transaction_sha256=transaction.transaction_sha256,
                published_head_sha256=head.head_sha256,
                commit_state="committed",
                committed_at_utc=fixed_now_utc,
            )
            self._atomic_write(
                self.receipts / f"{receipt.receipt_sha256}.json", receipt.model_dump(mode="json")
            )
            return head, receipt
