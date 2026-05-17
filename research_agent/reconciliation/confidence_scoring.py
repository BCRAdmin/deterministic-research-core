from __future__ import annotations


def score_confidence(source_rank: int, has_period: bool, has_unit: bool, is_reconciled: bool):
    score = 0
    if source_rank <= 2:
        score += 2
    elif source_rank <= 4:
        score += 1
    else:
        score -= 1
    if has_period:
        score += 1
    if has_unit:
        score += 1
    if is_reconciled:
        score += 1
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"
