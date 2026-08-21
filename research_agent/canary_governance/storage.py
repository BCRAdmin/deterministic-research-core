"""Research-owned durable ledgers and atomic authority-graph transactions."""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from research_agent.compiler_foundation.canonical import canonical_json, sha256_json

from .approval import TrustedRoleKeyPolicy, verify_approval, verify_independent_review
from .authority_graph import AuthorityGraphObjects, derive_promotion_subjects, verify_authority_graph
from .contracts import (
    AcceptedDebtEvent,
    ArchiveReceipt,
    CanaryFreezeRecord,
    ChangeClassification,
    CompareEngineReceipt,
    ComparisonRequest,
    ComparisonResult,
    DebtLedgerHead,
    GenesisImportHead,
    GenesisImportReceipt,
    GovernanceEnvelope,
    HashBoundModel,
    IndependentReviewAttestation,
    LedgerHeadPointer,
    OperatorApprovalReceipt,
    PromotionCandidate,
    PromotionEvent,
    RecoveryEvent,
    RegistryAuthorityGraph,
    RegistryCommitReceipt,
    RegistryEvent,
    RegistryHead,
    RegistryHeadPublicationPointer,
    RegistryLedgerHead,
    RegistryPreparedReceipt,
    RegistrySnapshot,
    RegistryTransaction,
    RejectionEvent,
    StaleEvent,
    SupersessionEvent,
    TechnicalBaseline,
    domain_hash,
)
from .diagnostics import CanaryGovernanceError
from .ledger import (
    build_debt_ledger_head,
    build_registry_ledger_head,
    fold_registry_events,
    verify_debt_ledger,
    verify_derived_snapshot,
)

ModelT = TypeVar("ModelT", bound=HashBoundModel)

REGISTRY_EVENT_MODELS = {
    "room16.canary_promotion_event": PromotionEvent,
    "room16.canary_rejection_event": RejectionEvent,
    "room16.canary_recovery_event": RecoveryEvent,
    "room16.canary_stale_event": StaleEvent,
    "room16.canary_supersession_event": SupersessionEvent,
    "room16.canary_registry_event": RegistryEvent,
}


class ContentAddressedRegistryStore:
    """Single-writer publication rail; Product receives immutable mirrors only."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = root / "objects" / "sha256"
        self.snapshots = root / "snapshots"
        self.transactions = root / "transactions"
        self.receipts = root / "receipts"
        self.registry_events = root / "ledger" / "registry" / "events"
        self.registry_heads = root / "ledger" / "registry" / "heads"
        self.registry_sets = root / "ledger" / "registry" / "sets"
        self.registry_pointer_path = root / "ledger" / "registry" / "current.json"
        self.debt_events = root / "ledger" / "debt" / "events"
        self.debt_heads = root / "ledger" / "debt" / "heads"
        self.debt_sets = root / "ledger" / "debt" / "sets"
        self.debt_pointer_path = root / "ledger" / "debt" / "current.json"
        self.genesis_head_path = root / "genesis" / "head.json"
        self.head_path = root / "heads" / "current.json"
        self.head_history = root / "heads" / "history"
        self.published_receipts = root / "heads" / "published_receipts"
        self.publication_pointer_path = root / "heads" / "publication_current.json"
        self.staging_transactions = root / "staging" / "transactions"
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

    def _write_immutable(self, path: Path, payload: dict[str, Any]) -> None:
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise CanaryGovernanceError("BA11_HASH_MISMATCH", str(path)) from exc
            if existing != payload:
                raise CanaryGovernanceError("BA11_HASH_MISMATCH", str(path))
            return
        self._atomic_write(path, payload)

    def put_immutable(self, payload: dict[str, Any]) -> str:
        """Persist a generic canonical JSON object by its raw content digest."""
        digest = sha256_json(payload)
        self._write_immutable(self.objects / f"{digest}.json", payload)
        return digest

    def _put_declared(self, model: HashBoundModel) -> str:
        digest = getattr(model, model.hash_field)
        self._write_immutable(self.objects / f"{digest}.json", model.model_dump(mode="json"))
        return digest

    @staticmethod
    def _read_model(path: Path, model_type):
        if not path.exists():
            return None
        try:
            return model_type.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError) as exc:
            raise CanaryGovernanceError("BA11_LEDGER_OBJECT_MISSING", str(path)) from exc

    def _load_declared(self, digest: str, model_type: type[ModelT]) -> ModelT:
        model = self._read_model(self.objects / f"{digest}.json", model_type)
        if model is None or getattr(model, model.hash_field) != digest:
            raise CanaryGovernanceError("BA11_RECOVERY_GRAPH_INCOMPLETE", digest)
        return model

    def read_head(self) -> RegistryHead | None:
        raw = self._read_model(self.head_path, RegistryHead)
        pointer = self._read_model(
            self.publication_pointer_path, RegistryHeadPublicationPointer
        )
        if raw is None and pointer is None:
            return None
        if raw is None or pointer is None:
            raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_pointer")
        receipts: dict[str, RegistryCommitReceipt] = {}
        try:
            for path in sorted(self.published_receipts.glob("*.json")):
                receipt = self._read_model(path, RegistryCommitReceipt)
                if (
                    receipt is None
                    or path.stem != receipt.receipt_sha256
                    or receipt.publication_state != "published"
                ):
                    raise ValueError(str(path))
                receipts[receipt.receipt_sha256] = receipt
        except (CanaryGovernanceError, ValueError) as exc:
            raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_receipt") from exc
        current_receipt = receipts.get(pointer.commit_receipt_sha256)
        if current_receipt is None:
            raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_receipt_missing")
        children: dict[str | None, set[str]] = {}
        for receipt in receipts.values():
            children.setdefault(receipt.previous_commit_receipt_sha256, set()).add(
                receipt.receipt_sha256
            )
        if any(len(values) > 1 for values in children.values()):
            raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_fork")
        if current_receipt.registry_generation != max(
            receipt.registry_generation for receipt in receipts.values()
        ):
            raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_generation")
        seen: set[str] = set()
        receipt = current_receipt
        authoritative_head = None
        while True:
            if receipt.receipt_sha256 in seen:
                raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_cycle")
            seen.add(receipt.receipt_sha256)
            head = self._read_model(
                self.head_history / f"{receipt.published_head_sha256}.json", RegistryHead
            )
            if (
                head is None
                or head.registry_generation != receipt.registry_generation
                or head.transaction_sha256 != receipt.transaction_sha256
                or head.authority_graph_sha256 != receipt.authority_graph_sha256
                or head.prepared_receipt_sha256 != receipt.prepared_receipt_sha256
                or head.previous_head_sha256 != receipt.previous_published_head_sha256
            ):
                raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_binding")
            authoritative_head = authoritative_head or head
            previous_receipt_sha = receipt.previous_commit_receipt_sha256
            if previous_receipt_sha is None:
                if receipt.registry_generation != 0 or receipt.previous_published_head_sha256 is not None:
                    raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_genesis")
                break
            previous_receipt = receipts.get(previous_receipt_sha)
            if (
                previous_receipt is None
                or previous_receipt.registry_generation + 1 != receipt.registry_generation
                or previous_receipt.published_head_sha256
                != receipt.previous_published_head_sha256
            ):
                raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_predecessor")
            receipt = previous_receipt
        if len(seen) != len(receipts):
            raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "unreachable_publication")
        if (
            pointer.registry_generation != current_receipt.registry_generation
            or pointer.published_head_sha256 != current_receipt.published_head_sha256
            or raw != authoritative_head
        ):
            raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "current_pointer")
        return raw

    def _current_publication_receipt(self) -> RegistryCommitReceipt | None:
        pointer = self._read_model(
            self.publication_pointer_path, RegistryHeadPublicationPointer
        )
        if pointer is None:
            return None
        receipt = self._read_model(
            self.published_receipts / f"{pointer.commit_receipt_sha256}.json",
            RegistryCommitReceipt,
        )
        if receipt is None:
            raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_receipt_missing")
        return receipt

    @staticmethod
    def _event_set_sha256(events: Iterable[RegistryEvent]) -> str:
        return domain_hash(
            "room16.canary_registry_event_set@1",
            [event.model_dump(mode="json") for event in events],
        )

    @staticmethod
    def _set_payload(kind: str, hashes: tuple[str, ...]) -> dict[str, Any]:
        return {
            "contract_id": "room16.canary_ledger_event_set",
            "schema_version": 1,
            "authority_owner": "research",
            "ledger_kind": kind,
            "event_sha256s": list(hashes),
        }

    def _persist_ledger(self, *, kind: str, events: tuple, head) -> None:
        event_root = self.registry_events if kind == "registry" else self.debt_events
        head_root = self.registry_heads if kind == "registry" else self.debt_heads
        set_root = self.registry_sets if kind == "registry" else self.debt_sets
        for event in events:
            self._put_declared(event)
            self._write_immutable(
                event_root / f"{event.event_sha256}.json", event.model_dump(mode="json")
            )
        self._put_declared(head)
        self._write_immutable(head_root / f"{head.head_sha256}.json", head.model_dump(mode="json"))
        self._write_immutable(
            set_root / f"{head.head_sha256}.json",
            self._set_payload(kind, tuple(event.event_sha256 for event in events)),
        )

    def _persist_staged_ledger(
        self, *, transaction_sha256: str, kind: str, events: tuple, head
    ) -> None:
        """Persist immutable candidates outside every published ledger namespace."""

        root = self.staging_transactions / transaction_sha256 / "ledger" / kind
        for event in events:
            self._put_declared(event)
            self._write_immutable(
                root / "events" / f"{event.event_sha256}.json",
                event.model_dump(mode="json"),
            )
        self._put_declared(head)
        self._write_immutable(
            root / "heads" / f"{head.head_sha256}.json", head.model_dump(mode="json")
        )
        self._write_immutable(
            root / "sets" / f"{head.head_sha256}.json",
            self._set_payload(kind, tuple(event.event_sha256 for event in events)),
        )

    def _read_event(self, kind: str, digest: str):
        root = self.registry_events if kind == "registry" else self.debt_events
        path = root / f"{digest}.json"
        if not path.exists():
            raise CanaryGovernanceError("BA11_LEDGER_OBJECT_MISSING", digest)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            selected = REGISTRY_EVENT_MODELS.get(raw.get("contract_id")) if kind == "registry" else AcceptedDebtEvent
            if selected is None:
                raise ValueError("unknown registry event contract")
            event = selected.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise CanaryGovernanceError("BA11_LEDGER_OBJECT_MISSING", digest) from exc
        if event.event_sha256 != digest:
            raise CanaryGovernanceError("BA11_HASH_MISMATCH", digest)
        return event

    def _read_ledger_set(self, kind: str, head_sha256: str) -> tuple:
        set_root = self.registry_sets if kind == "registry" else self.debt_sets
        path = set_root / f"{head_sha256}.json"
        if not path.exists():
            raise CanaryGovernanceError("BA11_LEDGER_OBJECT_MISSING", str(path))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            hashes = tuple(payload["event_sha256s"])
            if payload != self._set_payload(kind, hashes):
                raise ValueError("invalid event set")
            return tuple(self._read_event(kind, digest) for digest in hashes)
        except CanaryGovernanceError:
            raise
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise CanaryGovernanceError("BA11_LEDGER_OBJECT_MISSING", str(path)) from exc

    def _read_persistent_ledger(self, kind: str) -> tuple[tuple, Any] | None:
        pointer_path = self.registry_pointer_path if kind == "registry" else self.debt_pointer_path
        pointer = self._read_model(pointer_path, LedgerHeadPointer)
        if pointer is None:
            return None
        if pointer.ledger_kind != kind:
            raise CanaryGovernanceError("BA11_LEDGER_ROLLBACK", f"{kind}_pointer_kind")
        head_root = self.registry_heads if kind == "registry" else self.debt_heads
        head_type = RegistryLedgerHead if kind == "registry" else DebtLedgerHead
        head = self._read_model(head_root / f"{pointer.head_sha256}.json", head_type)
        if head is None or head.generation != pointer.generation:
            raise CanaryGovernanceError("BA11_LEDGER_ROLLBACK", f"{kind}_pointer")

        all_heads = []
        children: dict[str | None, set[str]] = {}
        for path in sorted(head_root.glob("*.json")):
            candidate = self._read_model(path, head_type)
            if candidate is None or path.stem != candidate.head_sha256:
                raise CanaryGovernanceError("BA11_HASH_MISMATCH", str(path))
            all_heads.append(candidate)
            children.setdefault(candidate.previous_head_sha256, set()).add(candidate.head_sha256)
        if any(len(items) > 1 for items in children.values()):
            raise CanaryGovernanceError("BA11_LEDGER_FORK", kind)
        maximum = max((candidate.generation for candidate in all_heads), default=-1)
        if head.generation != maximum:
            raise CanaryGovernanceError("BA11_LEDGER_ROLLBACK", kind)

        seen: set[str] = set()
        cursor = head
        while cursor.previous_head_sha256 is not None:
            if cursor.head_sha256 in seen:
                raise CanaryGovernanceError("BA11_LEDGER_FORK", f"{kind}_cycle")
            seen.add(cursor.head_sha256)
            previous = self._read_model(head_root / f"{cursor.previous_head_sha256}.json", head_type)
            if previous is None or previous.generation + 1 != cursor.generation:
                raise CanaryGovernanceError("BA11_LEDGER_OBJECT_MISSING", f"{kind}_predecessor")
            cursor = previous
        if cursor.generation != 0:
            raise CanaryGovernanceError("BA11_LEDGER_ROLLBACK", f"{kind}_genesis")

        events = self._read_ledger_set(kind, head.head_sha256)
        if kind == "registry":
            fold_registry_events(events, expected_head=head)
        else:
            actual = build_debt_ledger_head(
                events, generation=head.generation, previous_head_sha256=head.previous_head_sha256
            )
            if actual != head:
                raise CanaryGovernanceError("BA11_LEDGER_ROLLBACK", kind)
        return events, head

    def read_registry_ledger_head(self) -> RegistryLedgerHead | None:
        result = self._read_persistent_ledger("registry")
        return None if result is None else result[1]

    def read_debt_ledger_head(self) -> DebtLedgerHead | None:
        result = self._read_persistent_ledger("debt")
        return None if result is None else result[1]

    def _write_pointer(self, kind: str, head) -> None:
        path = self.registry_pointer_path if kind == "registry" else self.debt_pointer_path
        self._atomic_write(
            path,
            LedgerHeadPointer.create(
                ledger_kind=kind, head_sha256=head.head_sha256, generation=head.generation
            ).model_dump(mode="json"),
        )

    def append_registry_event(self, event: RegistryEvent, *, expected_head_sha256: str | None) -> RegistryLedgerHead:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self._read_persistent_ledger("registry")
            events, current_head = ((), None) if current is None else current
            current_hash = None if current_head is None else current_head.head_sha256
            if current_hash != expected_head_sha256:
                raise CanaryGovernanceError("BA11_LEDGER_FORK", "registry")
            prospective = (*events, event)
            head = build_registry_ledger_head(
                prospective,
                generation=0 if current_head is None else current_head.generation + 1,
                previous_head_sha256=current_hash,
            )
            fold_registry_events(prospective, expected_head=head)
            self._persist_ledger(kind="registry", events=prospective, head=head)
            self._write_pointer("registry", head)
            return head

    def append_debt_event(
        self,
        event: AcceptedDebtEvent,
        *,
        expected_head_sha256: str | None,
        authentic_approval_sha256s: set[str],
    ) -> DebtLedgerHead:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self._read_persistent_ledger("debt")
            events, current_head = ((), None) if current is None else current
            current_hash = None if current_head is None else current_head.head_sha256
            if current_hash != expected_head_sha256:
                raise CanaryGovernanceError("BA11_LEDGER_FORK", "debt")
            prospective = (*events, event)
            head = build_debt_ledger_head(
                prospective,
                generation=0 if current_head is None else current_head.generation + 1,
                previous_head_sha256=current_hash,
            )
            verify_debt_ledger(
                prospective,
                expected_head=head,
                authentic_approval_sha256s=authentic_approval_sha256s,
            )
            self._persist_ledger(kind="debt", events=prospective, head=head)
            self._write_pointer("debt", head)
            return head

    def commit_genesis_import(self, receipt: GenesisImportReceipt) -> GenesisImportHead:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if self.genesis_head_path.exists():
                raise CanaryGovernanceError("BA11_GENESIS_ALREADY_IMPORTED")
            self._put_declared(receipt)
            head = GenesisImportHead.create(import_receipt_sha256=receipt.receipt_sha256)
            self._write_immutable(self.genesis_head_path, head.model_dump(mode="json"))
            return head

    def _load_transaction(self, digest: str) -> RegistryTransaction:
        model = self._read_model(self.transactions / f"{digest}.json", RegistryTransaction)
        if model is None or model.transaction_sha256 != digest:
            raise CanaryGovernanceError("BA11_RECOVERY_GRAPH_INCOMPLETE", "transaction")
        return model

    def _replay_state_for_head(self, current: RegistryHead | None) -> tuple[set[str], int, int]:
        if current is None:
            return set(), 0, 0
        transaction = self._load_transaction(current.transaction_sha256)
        return set(transaction.consumed_nonces), current.operator_counter, current.reviewer_counter

    def _previous_replay_state(self, current: RegistryHead) -> tuple[set[str], int, int]:
        if current.previous_head_sha256 is None:
            return set(), 0, 0
        previous = self._read_model(self.head_history / f"{current.previous_head_sha256}.json", RegistryHead)
        if previous is None:
            raise CanaryGovernanceError("BA11_RECOVERY_GRAPH_INCOMPLETE", "previous_head")
        return self._replay_state_for_head(previous)

    def _load_registry_event_object(self, digest: str) -> RegistryEvent:
        path = self.objects / f"{digest}.json"
        if not path.exists():
            raise CanaryGovernanceError("BA11_RECOVERY_GRAPH_INCOMPLETE", digest)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            model_type = REGISTRY_EVENT_MODELS.get(raw.get("contract_id"))
            if model_type is None:
                raise ValueError("unknown event contract")
            event = model_type.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise CanaryGovernanceError("BA11_RECOVERY_GRAPH_INCOMPLETE", digest) from exc
        if event.event_sha256 != digest:
            raise CanaryGovernanceError("BA11_RECOVERY_GRAPH_INCOMPLETE", digest)
        return event

    def _load_authority_objects(self, graph: RegistryAuthorityGraph) -> AuthorityGraphObjects:
        return AuthorityGraphObjects(
            technical_baseline=self._load_declared(graph.technical_baseline_sha256, TechnicalBaseline),
            governance_envelope=self._load_declared(graph.governance_envelope_sha256, GovernanceEnvelope),
            promotion_candidate=self._load_declared(graph.promotion_candidate_sha256, PromotionCandidate),
            comparison_request=self._load_declared(graph.comparison_request_sha256, ComparisonRequest),
            compare_engine_receipt=self._load_declared(graph.compare_engine_receipt_sha256, CompareEngineReceipt),
            comparison_result=self._load_declared(graph.comparison_result_sha256, ComparisonResult),
            change_classification=self._load_declared(graph.change_classification_sha256, ChangeClassification),
            registry_events=tuple(self._load_registry_event_object(digest) for digest in graph.registry_event_sha256s),
            registry_ledger_head=self._load_declared(graph.registry_ledger_head_sha256, RegistryLedgerHead),
            debt_events=tuple(self._load_declared(digest, AcceptedDebtEvent) for digest in graph.debt_event_sha256s),
            debt_ledger_head=self._load_declared(graph.debt_ledger_head_sha256, DebtLedgerHead),
            freeze=self._load_declared(graph.freeze_sha256, CanaryFreezeRecord),
            independent_review=self._load_declared(graph.independent_review_sha256, IndependentReviewAttestation),
            operator_approval=self._load_declared(graph.operator_approval_sha256, OperatorApprovalReceipt),
            snapshot=self._load_declared(graph.candidate_snapshot_sha256, RegistrySnapshot),
            archive_receipt=self._load_declared(graph.archive_receipt_sha256, ArchiveReceipt),
        )

    def _verify_transaction_inputs(
        self,
        transaction: RegistryTransaction,
        graph: RegistryAuthorityGraph,
        objects: AuthorityGraphObjects,
        *,
        trusted_role_key_policy: TrustedRoleKeyPolicy,
        revoked_key_ids: set[str],
        fixed_now_utc: str,
        consumed_nonces: set[str],
        operator_counter: int,
        reviewer_counter: int,
    ) -> tuple[str, ...]:
        registry_hashes = tuple(event.event_sha256 for event in objects.registry_events)
        debt_hashes = tuple(event.event_sha256 for event in objects.debt_events)
        if registry_hashes != graph.registry_event_sha256s or debt_hashes != graph.debt_event_sha256s:
            raise CanaryGovernanceError("BA11_TRANSACTION_EVENT_AUTHORITY_MISSING")
        if transaction.registry_event_set_sha256 != self._event_set_sha256(objects.registry_events):
            raise CanaryGovernanceError("BA11_TRANSACTION_EVENT_AUTHORITY_MISSING")
        verify_derived_snapshot(objects.snapshot, objects.registry_events, expected_head=objects.registry_ledger_head)
        verify_debt_ledger(
            objects.debt_events,
            expected_head=objects.debt_ledger_head,
            authentic_approval_sha256s={objects.operator_approval.approval_sha256},
        )
        expected_ids, expected_hashes = derive_promotion_subjects(objects.promotion_candidate)
        previous_authority = transaction.base_head_sha256 or "0" * 64
        verify_independent_review(
            objects.independent_review,
            trusted_role_key_policy=trusted_role_key_policy,
            revoked_key_ids=revoked_key_ids,
            consumed_nonces=consumed_nonces,
            minimum_monotonic_counter=reviewer_counter,
            expected_decision="accepted",
            expected_scope="ba11_canary_promotion",
            expected_subject_ids=expected_ids,
            expected_subject_sha256s=expected_hashes,
            expected_finding_set_sha256=graph.finding_set_sha256,
            expected_previous_registry_head_sha256=previous_authority,
            fixed_now_utc=fixed_now_utc,
        )
        verify_approval(
            objects.operator_approval,
            trusted_role_key_policy=trusted_role_key_policy,
            revoked_key_ids=revoked_key_ids,
            consumed_nonces=consumed_nonces,
            minimum_monotonic_counter=operator_counter,
            expected_decision="approve",
            expected_scope="ba11_canary_promotion",
            expected_subject_ids=expected_ids,
            expected_subject_sha256s=expected_hashes,
            expected_finding_set_sha256=graph.finding_set_sha256,
            expected_previous_registry_head_sha256=previous_authority,
            fixed_now_utc=fixed_now_utc,
        )
        # Subject/base/finding diagnostics are intentionally resolved from the
        # graph before the remaining cross-object equality checks.
        verify_authority_graph(graph, transaction, objects)
        expected_nonces = tuple(sorted(consumed_nonces | {objects.operator_approval.nonce, objects.independent_review.nonce}))
        if (
            transaction.consumed_nonces != expected_nonces
            or transaction.operator_counter != objects.operator_approval.monotonic_counter
            or transaction.reviewer_counter != objects.independent_review.monotonic_counter
        ):
            raise CanaryGovernanceError("BA11_TRANSACTION_BINDING_INVALID", "replay_state")
        return expected_nonces

    def _recover_committed(
        self,
        current: RegistryHead,
        *,
        trusted_role_key_policy: TrustedRoleKeyPolicy,
        revoked_key_ids: set[str],
        fixed_now_utc: str,
    ) -> tuple[RegistryHead, RegistryCommitReceipt]:
        transaction = self._load_transaction(current.transaction_sha256)
        graph = self._load_declared(current.authority_graph_sha256, RegistryAuthorityGraph)
        objects = self._load_authority_objects(graph)
        prepared = self._read_model(
            self.receipts / f"{current.prepared_receipt_sha256}.json", RegistryPreparedReceipt
        )
        if (
            prepared is None
            or prepared.receipt_sha256 != current.prepared_receipt_sha256
            or prepared.transaction_sha256 != transaction.transaction_sha256
            or prepared.authority_graph_sha256 != graph.authority_graph_sha256
        ):
            raise CanaryGovernanceError("BA11_RECOVERY_GRAPH_INCOMPLETE", "prepared_receipt")
        consumed, operator_counter, reviewer_counter = self._previous_replay_state(current)
        self._verify_transaction_inputs(
            transaction,
            graph,
            objects,
            trusted_role_key_policy=trusted_role_key_policy,
            revoked_key_ids=revoked_key_ids,
            fixed_now_utc=fixed_now_utc,
            consumed_nonces=consumed,
            operator_counter=operator_counter,
            reviewer_counter=reviewer_counter,
        )
        expected_head = RegistryHead.create(
            registry_generation=transaction.registry_generation,
            previous_head_sha256=transaction.base_head_sha256,
            snapshot_sha256=objects.snapshot.snapshot_sha256,
            registry_ledger_head_sha256=objects.registry_ledger_head.head_sha256,
            debt_ledger_head_sha256=objects.debt_ledger_head.head_sha256,
            transaction_sha256=transaction.transaction_sha256,
            authority_graph_sha256=graph.authority_graph_sha256,
            prepared_receipt_sha256=prepared.receipt_sha256,
            consumed_nonce_set_sha256=domain_hash("room16.canary_nonce_set@1", transaction.consumed_nonces),
            operator_counter=transaction.operator_counter,
            reviewer_counter=transaction.reviewer_counter,
        )
        if expected_head != current:
            raise CanaryGovernanceError("BA11_RECOVERY_GRAPH_INCOMPLETE", "published_head")
        self._persist_ledger(kind="registry", events=objects.registry_events, head=objects.registry_ledger_head)
        self._persist_ledger(kind="debt", events=objects.debt_events, head=objects.debt_ledger_head)
        self._write_pointer("registry", objects.registry_ledger_head)
        self._write_pointer("debt", objects.debt_ledger_head)
        published_receipt = self._current_publication_receipt()
        if published_receipt is None:
            raise CanaryGovernanceError("BA11_REGISTRY_ROLLBACK", "publication_receipt_missing")
        receipt = RegistryCommitReceipt.create(
            registry_generation=current.registry_generation,
            previous_published_head_sha256=current.previous_head_sha256,
            previous_commit_receipt_sha256=published_receipt.receipt_sha256,
            transaction_sha256=transaction.transaction_sha256,
            published_head_sha256=current.head_sha256,
            authority_graph_sha256=graph.authority_graph_sha256,
            prepared_receipt_sha256=prepared.receipt_sha256,
            publication_state="recovery_evidence",
            commit_state="recovered",
            committed_at_utc=fixed_now_utc,
        )
        self._write_immutable(self.receipts / f"{receipt.receipt_sha256}.json", receipt.model_dump(mode="json"))
        return current, receipt

    def commit_transaction(
        self,
        transaction: RegistryTransaction,
        *,
        authority_graph: RegistryAuthorityGraph,
        authority_objects: AuthorityGraphObjects,
        trusted_role_key_policy: TrustedRoleKeyPolicy,
        revoked_key_ids: set[str],
        fixed_now_utc: str,
        fault: Callable[[str], None] | None = None,
    ) -> tuple[RegistryHead, RegistryCommitReceipt]:
        """Validate, persist and publish one complete authority graph atomically."""
        fault = fault or (lambda _step: None)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self.read_head()
            if current and current.transaction_sha256 == transaction.transaction_sha256:
                return self._recover_committed(
                    current,
                    trusted_role_key_policy=trusted_role_key_policy,
                    revoked_key_ids=revoked_key_ids,
                    fixed_now_utc=fixed_now_utc,
                )
            current_hash = None if current is None else current.head_sha256
            current_publication = self._current_publication_receipt()
            if current_hash != transaction.base_head_sha256:
                raise CanaryGovernanceError("BA11_REGISTRY_CAS_CONFLICT")
            expected_generation = 0 if current is None else current.registry_generation + 1
            if transaction.registry_generation != expected_generation:
                raise CanaryGovernanceError("BA11_REGISTRY_GENERATION_INVALID")
            previous_snapshot = None if current is None else current.snapshot_sha256
            if authority_objects.snapshot.previous_registry_sha256 != previous_snapshot:
                raise CanaryGovernanceError("BA11_REGISTRY_PREDECESSOR_INVALID")
            consumed, operator_counter, reviewer_counter = self._replay_state_for_head(current)
            expected_nonces = self._verify_transaction_inputs(
                transaction,
                authority_graph,
                authority_objects,
                trusted_role_key_policy=trusted_role_key_policy,
                revoked_key_ids=revoked_key_ids,
                fixed_now_utc=fixed_now_utc,
                consumed_nonces=consumed,
                operator_counter=operator_counter,
                reviewer_counter=reviewer_counter,
            )
            fault("before_immutable_staging")
            for model in (
                authority_objects.technical_baseline,
                authority_objects.governance_envelope,
                authority_objects.promotion_candidate,
                authority_objects.comparison_request,
                authority_objects.compare_engine_receipt,
                authority_objects.comparison_result,
                authority_objects.change_classification,
                *authority_objects.registry_events,
                authority_objects.registry_ledger_head,
                *authority_objects.debt_events,
                authority_objects.debt_ledger_head,
                authority_objects.freeze,
                authority_objects.independent_review,
                authority_objects.operator_approval,
                authority_objects.snapshot,
                authority_objects.archive_receipt,
                authority_graph,
                transaction,
            ):
                self._put_declared(model)
            self._persist_staged_ledger(
                transaction_sha256=transaction.transaction_sha256,
                kind="registry",
                events=authority_objects.registry_events,
                head=authority_objects.registry_ledger_head,
            )
            self._persist_staged_ledger(
                transaction_sha256=transaction.transaction_sha256,
                kind="debt",
                events=authority_objects.debt_events,
                head=authority_objects.debt_ledger_head,
            )
            self._write_immutable(
                self.snapshots / f"{authority_objects.snapshot.snapshot_sha256}.json",
                authority_objects.snapshot.model_dump(mode="json"),
            )
            self._write_immutable(
                self.transactions / f"{transaction.transaction_sha256}.json",
                transaction.model_dump(mode="json"),
            )
            fault("after_immutable_staging")
            prepared = RegistryPreparedReceipt.create(
                transaction_sha256=transaction.transaction_sha256,
                expected_base_head_sha256=current_hash,
                authority_graph_sha256=authority_graph.authority_graph_sha256,
                prepared_at_utc=fixed_now_utc,
            )
            self._put_declared(prepared)
            self._write_immutable(self.receipts / f"{prepared.receipt_sha256}.json", prepared.model_dump(mode="json"))
            fault("after_prepared_receipt")
            head = RegistryHead.create(
                registry_generation=transaction.registry_generation,
                previous_head_sha256=current_hash,
                snapshot_sha256=authority_objects.snapshot.snapshot_sha256,
                registry_ledger_head_sha256=authority_objects.registry_ledger_head.head_sha256,
                debt_ledger_head_sha256=authority_objects.debt_ledger_head.head_sha256,
                transaction_sha256=transaction.transaction_sha256,
                authority_graph_sha256=authority_graph.authority_graph_sha256,
                prepared_receipt_sha256=prepared.receipt_sha256,
                consumed_nonce_set_sha256=domain_hash("room16.canary_nonce_set@1", expected_nonces),
                operator_counter=authority_objects.operator_approval.monotonic_counter,
                reviewer_counter=authority_objects.independent_review.monotonic_counter,
            )
            self._put_declared(head)
            self._write_immutable(self.head_history / f"{head.head_sha256}.json", head.model_dump(mode="json"))
            receipt = RegistryCommitReceipt.create(
                registry_generation=head.registry_generation,
                previous_published_head_sha256=head.previous_head_sha256,
                previous_commit_receipt_sha256=(
                    None if current_publication is None else current_publication.receipt_sha256
                ),
                transaction_sha256=transaction.transaction_sha256,
                published_head_sha256=head.head_sha256,
                authority_graph_sha256=authority_graph.authority_graph_sha256,
                prepared_receipt_sha256=prepared.receipt_sha256,
                publication_state="published",
                commit_state="committed",
                committed_at_utc=fixed_now_utc,
            )
            self._put_declared(receipt)
            self._write_immutable(
                self.receipts / f"{receipt.receipt_sha256}.json",
                receipt.model_dump(mode="json"),
            )
            fault("before_head_swap")
            self._atomic_write(self.head_path, head.model_dump(mode="json"))
            self._persist_ledger(kind="registry", events=authority_objects.registry_events, head=authority_objects.registry_ledger_head)
            self._persist_ledger(kind="debt", events=authority_objects.debt_events, head=authority_objects.debt_ledger_head)
            self._write_pointer("registry", authority_objects.registry_ledger_head)
            self._write_pointer("debt", authority_objects.debt_ledger_head)
            self._write_immutable(
                self.published_receipts / f"{receipt.receipt_sha256}.json",
                receipt.model_dump(mode="json"),
            )
            self._atomic_write(
                self.publication_pointer_path,
                RegistryHeadPublicationPointer.create(
                    registry_generation=head.registry_generation,
                    published_head_sha256=head.head_sha256,
                    commit_receipt_sha256=receipt.receipt_sha256,
                ).model_dump(mode="json"),
            )
            fault("after_head_swap")
            if self.read_head() != head:
                raise CanaryGovernanceError("BA11_TRANSACTION_RECOVERY_INVALID", "head_readback")
            fault("after_readback")
            return head, receipt
