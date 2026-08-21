#!/usr/bin/env python3
"""Emit exact pytest node IDs from a real collect-only session."""

from __future__ import annotations

import json
import sys

import pytest


class NodeIdCollector:
    def __init__(self) -> None:
        self.nodeids: list[str] = []

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.nodeids = [item.nodeid for item in session.items]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: collect_pytest_nodeids.py <test-path>")
    collector = NodeIdCollector()
    exit_code = pytest.main(["--collect-only", "-q", sys.argv[1]], plugins=[collector])
    print(
        json.dumps(
            {
                "contract_id": "room16.pytest_collection_manifest_source@1",
                "nodeids": collector.nodeids,
                "pytest_exit_code": int(exit_code),
            },
            sort_keys=True,
        )
    )
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
