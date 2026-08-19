"""Fixed-clock and deterministic ZIP evidence primitives."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone

from research_agent.compiler_foundation.canonical import sha256_bytes, sha256_json


@dataclass(frozen=True)
class FixedClock:
    effective_at_utc: str

    def now(self) -> str:
        datetime.fromisoformat(self.effective_at_utc.replace("Z", "+00:00"))
        return self.effective_at_utc


def build_deterministic_zip(
    members: dict[str, bytes], *, source_date_epoch: int
) -> tuple[bytes, dict]:
    dt = datetime.fromtimestamp(source_date_epoch, tz=timezone.utc)
    zip_time = max((1980, 1, 1, 0, 0, 0), (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second))
    payload = []
    for name in sorted(members):
        if name.startswith("/") or ".." in name.split("/"):
            raise ValueError("unsafe archive path")
        payload.append({"path": name, "bytes": len(members[name]), "sha256": sha256_bytes(members[name])})
    manifest = {
        "contract_id": "room16.canary_evidence_manifest",
        "schema_version": 1,
        "payload_rule": "all members except MANIFEST.json",
        "self_excluded": True,
        "source_date_epoch": source_date_epoch,
        "files": payload,
    }
    manifest["manifest_sha256"] = sha256_json(manifest)
    complete = {**members, "MANIFEST.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(complete):
            info = zipfile.ZipInfo(name, date_time=zip_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, complete[name])
    return buffer.getvalue(), manifest
