from research_agent.reconciliation.unit_normalizer import (
    normalize_unit,
    normalize_value,
    validate_unit_for_metric,
)


def test_unit_normalizer_maps_common_sec_units():
    assert normalize_unit("USD") == "usd"
    assert normalize_unit("USD/share") == "usd_per_share"
    assert normalize_unit("shares") == "shares"
    assert normalize_unit("pure") == "ratio"


def test_normalize_value_returns_value_and_unit():
    value, unit = normalize_value(7.05, "USD/share")

    assert value == 7.05
    assert unit == "usd_per_share"


def test_suspicious_eps_unit_warns():
    issue = validate_unit_for_metric("eps_diluted", "USD")

    assert issue["code"] == "SUSPICIOUS_EPS_UNIT"
