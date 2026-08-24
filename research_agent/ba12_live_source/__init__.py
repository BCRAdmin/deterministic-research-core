"""RFC-0010 additive live-capture transport upstream of frozen BA3."""

from .adapter_harness import ExistingAdapterHarness, normalize_adapter_result
from .authority_store import LiveAuthorityStore, RecoveredLiveRun
from .ba3_bridge import (
    LiveBridgeResult,
    bridge_capture_set_to_ba3,
    close_failed_capture_run,
)
from .capture_store import ContentAddressedCaptureStore
from .contracts import (
    LiveCaptureArtifact,
    LiveAttemptRecord,
    LiveCaptureBinding,
    LiveCaptureDisposition,
    LiveCaptureError,
    LiveCaptureSet,
    LiveRetrievalReceipt,
    LiveRunClosure,
)
from .live_receipt import (
    LiveCaptureExecutor,
    LiveCaptureRecord,
    ProviderResponse,
    classify_provider_status,
)
from .recovery import load_closed_run, recover_after_capture, recover_bridge
from .verifier import verify_authority_boundary, verify_live_bridge

__all__ = [
    "ContentAddressedCaptureStore",
    "ExistingAdapterHarness",
    "LiveAttemptRecord",
    "LiveAuthorityStore",
    "LiveBridgeResult",
    "LiveCaptureArtifact",
    "LiveCaptureBinding",
    "LiveCaptureDisposition",
    "LiveCaptureError",
    "LiveCaptureExecutor",
    "LiveCaptureRecord",
    "LiveCaptureSet",
    "LiveRetrievalReceipt",
    "LiveRunClosure",
    "ProviderResponse",
    "RecoveredLiveRun",
    "bridge_capture_set_to_ba3",
    "classify_provider_status",
    "close_failed_capture_run",
    "load_closed_run",
    "normalize_adapter_result",
    "recover_after_capture",
    "recover_bridge",
    "verify_authority_boundary",
    "verify_live_bridge",
]
