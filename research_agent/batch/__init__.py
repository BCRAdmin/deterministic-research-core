"""Batch orchestration helpers for deterministic research pipeline runs."""

from research_agent.batch.artifact_index import ARTIFACT_NAMES, build_artifact_index
from research_agent.batch.batch_config import BatchConfig, BatchTickerConfig, load_batch_config
from research_agent.batch.batch_manifest import BatchManifest, BatchRunItem
from research_agent.batch.dashboard_adapter import build_dashboard_status, save_dashboard_status

__all__ = [
    "ARTIFACT_NAMES",
    "BatchConfig",
    "BatchManifest",
    "BatchRunItem",
    "BatchRunner",
    "BatchTickerConfig",
    "build_artifact_index",
    "build_dashboard_status",
    "load_batch_config",
    "save_dashboard_status",
]


def __getattr__(name: str):
    if name == "BatchRunner":
        from research_agent.batch.batch_runner import BatchRunner

        return BatchRunner
    raise AttributeError(name)
