# Customer Contract Validation

- Contract: `/Users/colbyreichenbach/Downloads/shelfops_project/contracts/productization/enterprise_like_v1.yaml`
- Sample: `/Users/colbyreichenbach/Downloads/shelfops_project/backend/tests/fixtures/contracts/enterprise_like`
- Rows input: 2
- Rows mapped: 2
- Passed: `True`
- Canonical required fields present: `True`

## Metrics

| metric | value | threshold |
|---|---:|---:|
| date_parse_success | 1.0000 | >= 0.9900 |
| required_null_rate | 0.0000 | <= 0.0050 |
| duplicate_rate | 0.0000 | <= 0.0100 |
| quantity_parse_success | 1.0000 | >= 0.9950 |
| requires_custom_adapter | 0 | 0 = no |

## Semantic DQ

- max_future_days_observed: -44.00
- history_years_observed: 0.12
- store_ref_missing_rate: 0.0000
- product_ref_missing_rate: 0.0000

## Cost Field Confidence

- unit_cost_non_null_rate: 0.0000
- unit_cost_confidence: `unavailable`
- unit_price_non_null_rate: 1.0000
- unit_price_confidence: `measured`

## Failures

- None

## Notes

- Pass/fail thresholds are enforced from the contract profile dq_thresholds with strict defaults.
- This validator gates onboarding before candidate retraining.
