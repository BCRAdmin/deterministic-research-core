# Archetype Sanity Review

Batch: `archetype_sanity_check`
As of: `2026-05-16`

| Ticker | Erwartung | Archetype | Confidence | Status | Publishable | External Display | Top Triggered Rules |
|---|---|---:|---:|---|---:|---|---|
| RGTI | Deep-Tech manual_review | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | 1.000 | manual_review | False | Manual Review / Preliminary Underweight | market_cap_revenue_gt_100, revenue_ttm_lt_50m, operating_income_ttm_lt_0, free_cash_flow_ttm_lt_0, sbc_to_revenue_gt_050 |
| IONQ | Deep-Tech pruefen | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | 1.000 | manual_review | False | Manual Review / Preliminary Underweight | market_cap_revenue_gt_100, revenue_ttm_lt_50m, operating_income_ttm_lt_0, free_cash_flow_ttm_lt_0, sbc_to_revenue_gt_050 |
| QBTS | Deep-Tech pruefen | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | 1.000 | manual_review | False | Manual Review / Preliminary Underweight | market_cap_revenue_gt_100, revenue_ttm_lt_50m, operating_income_ttm_lt_0, free_cash_flow_ttm_lt_0, sbc_to_revenue_gt_050 |
| RKLB | Early-commercial capital-intensive tech | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH | 1.000 | manual_review | False | Manual Review / Hold Pending FCF and Execution Evidence | revenue_ttm_gt_100m, revenue_ttm_lt_5b, operating_income_ttm_lt_0, free_cash_flow_ttm_lt_0, market_cap_revenue_gt_20 |
| GOOGL | Mega-Cap kein Deep-Tech | MEGA_CAP_PLATFORM | 0.200 | passed | True | Hold |  |
| SNOW | SaaS kein Deep-Tech | SAAS_CONSUMPTION | 0.200 | passed | True | Hold | operating_income_ttm_lt_0 |
| MSFT | Mega-Cap kein Deep-Tech | MEGA_CAP_PLATFORM | 0.200 | passed | True | Hold |  |
| QCOM | Semiconductor, FCF Display-Regel | SEMICONDUCTOR_AI_INFRA | 0.200 | manual_review | False | Hold Pending FCF Support |  |

## Ergebnis

- Deep-Tech Profile Count: 3
- Early-Commercial Capital-Intensive Tech Count: 1
- Vendor-only Hard Metrics Count: 3
- Accounting-Gain Guard Count: 3
- Order Materiality Missing Count: 3
- Technical Overweight Count: 1

## Sanity-Urteil

- RGTI bleibt `manual_review` und wird als `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL` erkannt.
- IONQ und QBTS lösen ebenfalls generisch aus, weil mehrere frühe Deep-Tech-, Microcap-/Story-Stock- und Evidence-Risiken zusammenkommen.
- RKLB-artige Space-/Hardware-Fälle mit Umsatz, Backlog und Execution-Risiko laufen als `EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH` und zeigen `Manual Review / Hold Pending FCF and Execution Evidence`.
- GOOGL, SNOW und MSFT werden nicht als Deep-Tech klassifiziert.
- QCOM bleibt `SEMICONDUCTOR_AI_INFRA`; die FCF-Support-Display-Regel bleibt sichtbar mit `Hold Pending FCF Support`.
- Keine Guard-Lockerung und keine neue Architektur: der Batch nutzt die bestehende Audit-/Quality-/Dashboard-Schicht.
