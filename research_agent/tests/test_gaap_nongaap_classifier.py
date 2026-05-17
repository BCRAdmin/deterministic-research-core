from research_agent.reconciliation.gaap_nongaap_classifier import classify_metric_basis


def test_sec_facts_classify_as_gaap():
    assert classify_metric_basis("sec_filing", "eps_diluted") == "gaap"


def test_non_gaap_text_classifies_as_non_gaap():
    assert classify_metric_basis("earnings_release", "operating_income", "Adjusted non-GAAP operating income") == "non_gaap"


def test_consensus_provider_classifies_as_consensus():
    assert classify_metric_basis("market_data_provider", "consensus_forward_eps") == "consensus"


def test_guidance_without_non_gaap_is_company_defined():
    assert classify_metric_basis("company_ir", "company_guidance_eps", "EPS guidance") == "company_defined"
