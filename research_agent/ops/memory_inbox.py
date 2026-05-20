"""Memory inbox and local session-search artifacts.

This module keeps Hermes-style memory convenience behind an Obsidian-compatible
promotion gate. It proposes candidate memories and builds a local searchable
index; it never writes canonical Obsidian notes.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_MEMORY_TARGETS = (
    "docs",
    "outputs/skill_intake",
    "outputs/skill_playbooks",
    "outputs/utility_websites",
    "outputs/quellwert_room16_operating",
)

SKIP_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
}

MEMORY_MARKERS = (
    "Learning:",
    "Dauerregel:",
    "First Mention",
    "Naechster sinnvoller Schnitt",
    "Next step",
    "Operator-Gate",
    "Guardrail",
    "Hermes",
    "OpenClaw",
    "Vivi",
    "Vega",
)


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    source_path: str
    line: int
    kind: str
    route: str
    status: str
    summary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SearchHit:
    path: str
    line: int
    snippet: str
    score: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def iter_markdown_files(root: Path, targets: Sequence[str] = DEFAULT_MEMORY_TARGETS) -> Iterable[Path]:
    for target in targets:
        start = root / target
        if not start.exists():
            continue
        if start.is_file() and start.suffix.lower() == ".md":
            yield start
            continue
        if not start.is_dir():
            continue
        for current_root, dirnames, filenames in os.walk(start):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
            for filename in filenames:
                path = Path(current_root) / filename
                if path.suffix.lower() == ".md":
                    yield path


def _classify_candidate(line: str) -> tuple[str, str]:
    lower = line.lower()
    if "first mention" in lower:
        return ("first_mention", "Memory/First Mention Register")
    if "operator-gate" in lower or "gate" in lower:
        return ("operator_gate_learning", "Memory/Learnings and Fixes")
    if "hermes" in lower or "openclaw" in lower:
        return ("agent_stack_learning", "DreamFactory System/Agent Stack")
    if "vivi" in lower or "vega" in lower:
        return ("workflow_learning", "Memory/Learnings and Fixes")
    return ("general_learning", "Memory/Learnings and Fixes")


def collect_memory_candidates(
    root: Path,
    targets: Sequence[str] = DEFAULT_MEMORY_TARGETS,
    limit_per_file: int = 25,
) -> list[MemoryCandidate]:
    root = root.resolve()
    candidates: list[MemoryCandidate] = []
    seen: set[str] = set()
    for path in sorted(set(iter_markdown_files(root, targets))):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = str(path.resolve().relative_to(root))
        per_file = 0
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped:
                continue
            if not any(marker.lower() in stripped.lower() for marker in MEMORY_MARKERS):
                continue
            if len(stripped) < 24:
                continue
            kind, route = _classify_candidate(stripped)
            summary = stripped.lstrip("-*# ").strip()[:360]
            digest = hashlib.sha1(f"{rel}:{line_number}:{summary}".encode("utf-8")).hexdigest()[:12]
            if digest in seen:
                continue
            seen.add(digest)
            candidates.append(
                MemoryCandidate(
                    candidate_id=f"mem-{digest}",
                    source_path=rel,
                    line=line_number,
                    kind=kind,
                    route=route,
                    status="candidate_needs_promotion_review",
                    summary=summary,
                )
            )
            per_file += 1
            if per_file >= limit_per_file:
                break
    return candidates


def build_search_index(root: Path, db_path: Path, targets: Sequence[str] = DEFAULT_MEMORY_TARGETS) -> int:
    """Build a local SQLite search index and return indexed row count."""

    root = root.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DROP TABLE IF EXISTS docs")
        conn.execute("CREATE TABLE docs(path TEXT NOT NULL, line INTEGER NOT NULL, content TEXT NOT NULL)")
        try:
            conn.execute("CREATE VIRTUAL TABLE docs_fts USING fts5(path, content)")
            use_fts = True
        except sqlite3.OperationalError:
            use_fts = False
        count = 0
        for path in sorted(set(iter_markdown_files(root, targets))):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = str(path.resolve().relative_to(root))
            for line_number, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if not stripped:
                    continue
                conn.execute(
                    "INSERT INTO docs(path, line, content) VALUES (?, ?, ?)",
                    (rel, line_number, stripped),
                )
                if use_fts:
                    conn.execute(
                        "INSERT INTO docs_fts(rowid, path, content) VALUES (last_insert_rowid(), ?, ?)",
                        (rel, stripped),
                    )
                count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def search_index(db_path: Path, query: str, limit: int = 10) -> list[SearchHit]:
    conn = sqlite3.connect(db_path)
    try:
        has_fts = bool(
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='docs_fts'"
            ).fetchone()
        )
        if has_fts:
            rows = conn.execute(
                """
                SELECT d.path, d.line, d.content, bm25(docs_fts) AS score
                FROM docs_fts
                JOIN docs d ON d.rowid = docs_fts.rowid
                WHERE docs_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT path, line, content, 0.0 AS score
                FROM docs
                WHERE lower(content) LIKE lower(?)
                LIMIT ?
                """,
                (f"%{query}%", limit),
            ).fetchall()
    finally:
        conn.close()
    return [
        SearchHit(path=row[0], line=int(row[1]), snippet=str(row[2])[:360], score=float(row[3]))
        for row in rows
    ]


def render_candidates_markdown(candidates: Sequence[MemoryCandidate]) -> str:
    lines = [
        "# Memory Inbox Candidates",
        "",
        "These are promotion candidates. They are not canonical memory until reviewed.",
        "",
        f"Candidates: {len(candidates)}",
        "",
        "| Candidate | Route | Kind | Source | Line | Summary |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for item in candidates:
        lines.append(
            f"| `{item.candidate_id}` | `{item.route}` | `{item.kind}` | "
            f"`{item.source_path}` | {item.line} | {item.summary} |"
        )
    return "\n".join(lines) + "\n"
