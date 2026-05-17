from research_agent.batch.archetype_sanity import run_archetype_sanity_batch


def test_archetype_sanity_batch_outputs_expected_dashboard(tmp_path):
    dashboard = run_archetype_sanity_batch(tmp_path / "archetype_sanity_check")
    items = {item["ticker"]: item for item in dashboard["items"]}

    assert (tmp_path / "archetype_sanity_check" / "dashboard_status.json").exists()
    assert (tmp_path / "archetype_sanity_check" / "archetype_sanity_review.md").exists()

    assert items["RGTI"]["company_archetype"] == "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL"
    assert items["RGTI"]["status"] == "manual_review"
    assert items["RGTI"]["publishable"] is False
    assert items["RGTI"]["display_rating"] == "Manual Review / Preliminary Underweight"

    assert items["IONQ"]["company_archetype"] == "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL"
    assert items["QBTS"]["company_archetype"] == "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL"
    assert items["RKLB"]["company_archetype"] == "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH"
    assert items["RKLB"]["status"] == "manual_review"
    assert items["RKLB"]["publishable"] is False
    assert items["RKLB"]["display_rating"] == "Manual Review / Hold Pending FCF and Execution Evidence"

    assert items["GOOGL"]["company_archetype"] == "MEGA_CAP_PLATFORM"
    assert items["SNOW"]["company_archetype"] == "SAAS_CONSUMPTION"
    assert items["MSFT"]["company_archetype"] == "MEGA_CAP_PLATFORM"
    assert items["QCOM"]["company_archetype"] == "SEMICONDUCTOR_AI_INFRA"
    assert items["QCOM"]["display_rating"] == "Hold Pending FCF Support"

    assert dashboard["summary"]["speculative_deep_tech_profile_count"] == 3
    assert dashboard["summary"]["early_commercial_capital_intensive_tech_count"] == 1
    assert dashboard["summary"]["vendor_only_hard_metrics_count"] == 3
    assert dashboard["summary"]["manual_review"] == 5
