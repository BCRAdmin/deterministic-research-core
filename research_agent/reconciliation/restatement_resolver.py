from __future__ import annotations


AMENDED_FORMS = {"10-K/A", "10-Q/A"}


def is_amended_form(form: str | None) -> bool:
    return form in AMENDED_FORMS


def prefer_restatement(facts):
    grouped = {}
    for fact in facts:
        key = (fact.metric_name, fact.fy, fact.fp, fact.start, fact.end)
        grouped.setdefault(key, []).append(fact)

    selected = []
    for candidates in grouped.values():
        amended = [fact for fact in candidates if is_amended_form(fact.form)]
        if amended:
            selected.append(sorted(amended, key=lambda fact: fact.filed or "")[-1])
        else:
            selected.append(sorted(candidates, key=lambda fact: fact.filed or "")[-1])
    return selected
