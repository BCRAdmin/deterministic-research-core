# Lifecycle / Promotion Regression

Status: pass. Markdown-first QA, Internal Best, and Public Final remain separated. No report was found public_ready without Promotion.

| Lane | Result |
| --- | --- |
| Markdown-first QA | draft_markdown_qa / markdown_first_qa / public_ready=False / final_documents_rendered=False |
| Internal Best | RGTI sample lane=internal_best / public_ready=False / publish_report=None |
| Public Final | requires_promotion_gate=True / unattended_publish_ready=False |
| Promotion | sample public_ready=False / reasons=['approval_timestamp_missing', 'final_documents_not_rendered', 'generation_stage_not_public_final', 'human_approval_missing', 'non_advice_confirmation_missing', 'promotion_status_missing', 'public_visibility_not_requested', 'publish_report_missing', 'sources_human_verification_missing'] |
