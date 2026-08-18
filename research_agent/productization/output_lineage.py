"""Deterministic visible-output lineage for BA10 compatibility rendering.

The lineage does not promote legacy report prose to new compiler truth.  It
binds every visible Markdown line and every visible numeric token to an exact
compiler-owned display token.  Existing Room16 lineage comments additionally
bind spans to compiler claim identifiers.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from research_agent.compiler_foundation.canonical import sha256_json

LINEAGE_CONTRACT_ID = "room16.rendered_output_lineage"
LINEAGE_CONTRACT_VERSION = 1
LINEAGE_ALGORITHM = "room16.markdown_visible_spans@1"
COMMENT_PATTERN = re.compile(r"<!--(.*?)-->")
CLAIM_PATTERN = re.compile(r"\bclaim=([A-Z0-9._-]+)")
DECISION_PATTERN = re.compile(r"\bdecision=([A-Za-z0-9._:-]+)")
FACT_PATTERN = re.compile(r"\bfact=([A-Za-z0-9._:-]+)")
EVIDENCE_PATTERN = re.compile(r"\bevidence=([A-Za-z0-9._:,-]+)")
CLAIM_ROW_PATTERN = re.compile(r"\|\s*([A-Z0-9._-]+_CLAIM_\d{3})\s*\|")
NUMERIC_PATTERN = re.compile(r"[-+]?\d[\d.,]*(?:%|[xX]|[KMBT])?")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\|?(?:\s*:?-+:?\s*\|)+\s*$")


def _unique(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value})


def _refs(pattern: re.Pattern[str], comments: str) -> list[str]:
    return _unique(pattern.findall(comments))


def _evidence_refs(comments: str) -> list[str]:
    values: list[str] = []
    for packed in EVIDENCE_PATTERN.findall(comments):
        values.extend(item for item in packed.split(",") if item)
    return _unique(values)


def build_rendered_output_lineage(
    markdown: str,
    *,
    source_markdown_sha256: str,
    allowed_fact_ids: Iterable[str],
    allowed_claim_ids: Iterable[str],
    allowed_decision_ids: Iterable[str],
) -> dict[str, Any]:
    """Return canonical visible spans derived only from exact Markdown bytes."""

    if "\r" in markdown:
        raise ValueError("RENDERER_LINE_ENDING_UNSUPPORTED")
    allowed_facts = set(allowed_fact_ids)
    allowed_claims = set(allowed_claim_ids)
    allowed_decisions = set(allowed_decision_ids)
    material_spans: list[dict[str, Any]] = []
    numeric_spans: list[dict[str, Any]] = []
    display_tokens: list[dict[str, Any]] = []
    byte_cursor = 0

    for line_number, raw_line in enumerate(markdown.split("\n"), start=1):
        line_byte_length = len(raw_line.encode("utf-8"))
        comments = " ".join(COMMENT_PATTERN.findall(raw_line))
        visible_text = COMMENT_PATTERN.sub("", raw_line).strip()
        if (
            not visible_text
            or visible_text == "---"
            or TABLE_SEPARATOR_PATTERN.fullmatch(visible_text)
        ):
            byte_cursor += line_byte_length + 1
            continue

        claim_refs = _refs(CLAIM_PATTERN, comments)
        claim_refs.extend(CLAIM_ROW_PATTERN.findall(visible_text))
        claim_refs = _unique(claim_refs)
        fact_refs = _refs(FACT_PATTERN, comments)
        decision_refs = _refs(DECISION_PATTERN, comments)
        unknown_claims = sorted(set(claim_refs) - allowed_claims)
        unknown_facts = sorted(set(fact_refs) - allowed_facts)
        unknown_decisions = sorted(set(decision_refs) - allowed_decisions)
        if unknown_claims or unknown_facts or unknown_decisions:
            raise ValueError(
                "RENDERER_LINEAGE_REFERENCE_UNKNOWN:"
                f"claims={unknown_claims}:facts={unknown_facts}:decisions={unknown_decisions}"
            )

        span_seed = {
            "line_number": line_number,
            "source_byte_start": byte_cursor,
            "source_byte_end": byte_cursor + line_byte_length,
            "visible_text_sha256": sha256_json(visible_text),
        }
        span_id = f"span.{sha256_json(span_seed)[:24]}"
        display_token_id = f"display.{span_id}"
        span = {
            "span_id": span_id,
            "line_number": line_number,
            "source_byte_start": byte_cursor,
            "source_byte_end": byte_cursor + line_byte_length,
            "source_line_sha256": sha256_json(raw_line),
            "visible_text_sha256": sha256_json(visible_text),
            "display_token_id": display_token_id,
            "fact_refs": fact_refs,
            "claim_refs": claim_refs,
            "decision_refs": decision_refs,
            "evidence_refs": _evidence_refs(comments),
            "binding_mode": (
                "compiler_claim_or_decision_bound"
                if claim_refs or fact_refs or decision_refs
                else "exact_compatibility_display_span"
            ),
        }
        material_spans.append(span)
        display_tokens.append(
            {
                "token_id": display_token_id,
                "token_type": "material_span",
                "span_id": span_id,
                "visible_text_sha256": span["visible_text_sha256"],
            }
        )

        for ordinal, match in enumerate(NUMERIC_PATTERN.finditer(visible_text), start=1):
            numeric_seed = {
                "span_id": span_id,
                "ordinal": ordinal,
                "start": match.start(),
                "end": match.end(),
                "text_sha256": sha256_json(match.group(0)),
            }
            numeric_id = f"numeric.{sha256_json(numeric_seed)[:24]}"
            numeric_token_id = f"display.{numeric_id}"
            numeric_spans.append(
                {
                    "numeric_span_id": numeric_id,
                    "parent_span_id": span_id,
                    "ordinal": ordinal,
                    "visible_char_start": match.start(),
                    "visible_char_end": match.end(),
                    "visible_text_sha256": sha256_json(match.group(0)),
                    "display_token_id": numeric_token_id,
                }
            )
            display_tokens.append(
                {
                    "token_id": numeric_token_id,
                    "token_type": "numeric_span",
                    "span_id": span_id,
                    "visible_text_sha256": sha256_json(match.group(0)),
                }
            )
        byte_cursor += line_byte_length + 1

    body = {
        "contract_id": LINEAGE_CONTRACT_ID,
        "contract_version": LINEAGE_CONTRACT_VERSION,
        "algorithm": LINEAGE_ALGORITHM,
        "source_markdown_sha256": source_markdown_sha256,
        "material_spans": material_spans,
        "numeric_spans": numeric_spans,
        "display_tokens": sorted(display_tokens, key=lambda item: item["token_id"]),
        "visible_material_span_count": len(material_spans),
        "visible_numeric_span_count": len(numeric_spans),
        "unbound_visible_span_count": 0,
        "compatibility_shadow": True,
        "semantic_promotion": False,
    }
    return {**body, "ir_sha256": sha256_json(body)}
