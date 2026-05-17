from __future__ import annotations


def deduplicate_facts(facts):
    grouped = {}
    for fact in facts:
        key = (
            fact.metric_name,
            fact.fy,
            fact.fp,
            fact.start,
            fact.end,
            fact.unit,
            getattr(fact, "frame", None),
            getattr(fact, "concept", None),
        )
        grouped.setdefault(key, []).append(fact)

    selected = []
    warnings = []
    for key, candidates in grouped.items():
        candidates_sorted = sorted(
            candidates,
            key=lambda fact: (
                fact.filed or "",
                _form_priority(fact.form, fact.fp),
            ),
            reverse=True,
        )
        values = {candidate.value for candidate in candidates}
        if len(values) > 1:
            warnings.append({
                "severity": "warning",
                "code": "DUPLICATE_FACT_VALUE_MISMATCH",
                "metric": key[0],
                "message": f"Duplicate facts have different values for {key}.",
            })
        selected.append(candidates_sorted[0])
    return selected, warnings


def _form_priority(form: str | None, fp: str | None) -> int:
    if fp in {"FY", "CY"} and form in {"10-K", "10-K/A"}:
        return 3
    if fp not in {"FY", "CY"} and form in {"10-Q", "10-Q/A"}:
        return 3
    if form in {"10-K", "10-Q", "10-K/A", "10-Q/A"}:
        return 2
    return 1
