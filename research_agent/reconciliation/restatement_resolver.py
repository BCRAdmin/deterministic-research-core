from __future__ import annotations


AMENDED_FORMS = {"10-K/A", "10-Q/A"}


def is_amended_form(form: str | None) -> bool:
    return form in AMENDED_FORMS


def prefer_restatement(facts):
    grouped = {}
    for fact in facts:
        if getattr(fact, "source_type", None) == "sec_filing":
            # SEC comparative facts can be repeated under the newer filing's
            # fiscal labels or frame even though their real measurement dates
            # are unchanged.  The latest filing is the authoritative
            # retrospective presentation for that exact concept and period.
            key = (
                fact.source_type,
                fact.metric_name,
                fact.start,
                fact.end,
                fact.unit,
                getattr(fact, "concept", None),
            )
        else:
            key = (
                getattr(fact, "source_type", None),
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
    for candidates in grouped.values():
        selected.append(
            sorted(
                candidates,
                key=lambda fact: (
                    fact.filed or "",
                    int(is_amended_form(fact.form)),
                ),
            )[-1]
        )
    return selected
