# ShelfOps Data Contract Specification

- Last verified date: February 15, 2026
- Audience: data engineering, onboarding, ML engineering
- Scope: contract schema, semantic controls, and validation gates
- Source of truth: `backend/ml/contract_profiles.py`, `backend/ml/contract_mapper.py`

## Contract Location and Versioning

- Profiles live at `contracts/<tenant>/<source>/v1.yaml` (`implemented`).
- Supported source types: `smb_csv`, `smb_sftp`, `enterprise_edi`, `enterprise_sftp`, `enterprise_event` (`implemented`).

## Required Contract Fields

- `contract_version`, `tenant_id`, `source_type`, `grain`, `timezone`
- `timezone_handling`, `quantity_sign_policy`
- `id_columns`, `field_map`, `type_map`, `unit_map`
- `null_policy`, `dedupe_keys`, `dq_thresholds`

Status: `implemented`

## Canonical Transaction Fields

- Required: `date`, `store_id`, `product_id`, `quantity` (`implemented`)
- Required metadata: `tenant_id`, `source_type`, `frequency`, `country_code` (`implemented`)
- Optional business fields: `unit_cost`, `unit_price`, `on_hand_qty`, `on_order_qty`, `category` (`implemented`)

## Semantic Controls

- `timezone_handling`: `source_local_date`, `convert_to_profile_tz_date`, `utc_date` (`implemented`)
- `quantity_sign_policy`: `non_negative`, `allow_negative_returns`, `clip_negative` (`implemented`)

## Quality Gates

DQ thresholds are enforced during validation and onboarding promotion checks (`implemented`).

## Validation Surfaces

- CLI validator: `backend/scripts/validate_customer_contract.py` (`implemented`)
- Onboarding flow: `backend/scripts/run_onboarding_flow.py` (`implemented`)
