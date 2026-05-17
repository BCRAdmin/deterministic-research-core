from research_agent.batch.batch_manifest import BatchRunItem
from research_agent.batch.batch_status import final_batch_status, status_from_result


def test_batch_status_from_result_recognizes_repaired():
    result = {
        "repaired": True,
        "publishable": True,
    }

    assert status_from_result(result) == "repaired"


def test_final_batch_status_completed_with_issues():
    status = final_batch_status(
        [
            BatchRunItem(ticker="AMZN", status="passed"),
            BatchRunItem(ticker="MDB", status="manual_review"),
        ]
    )

    assert status == "completed_with_issues"


def test_final_batch_status_data_unavailable_is_completed_with_issues():
    status = final_batch_status(
        [
            BatchRunItem(ticker="GOOGL", status="passed"),
            BatchRunItem(ticker="RKLB", status="data_unavailable"),
        ]
    )

    assert status == "completed_with_issues"
