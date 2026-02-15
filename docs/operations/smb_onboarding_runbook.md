# ShelfOps SMB Onboarding Runbook

- Last verified date: February 15, 2026
- Audience: onboarding, ops, data engineering
- Scope: SMB CSV/SFTP onboarding path
- Source of truth: contract profiles and onboarding scripts

## Workflow

1. Receive source sample extract (`implemented`).
2. Author or approve tenant profile at `contracts/<tenant>/<source>/v1.yaml` (`implemented`).
3. Run validation gate (`implemented`).
4. Canonicalize and run candidate training path (`implemented`).
5. Promote only through DS + business gates (`implemented`).

## Verified Invocation Surfaces

```bash
PYTHONPATH=backend python3 backend/scripts/validate_customer_contract.py --help
PYTHONPATH=backend python3 backend/scripts/run_onboarding_flow.py --help
```

## SLA Intent

- First valid forecast candidate within 3-5 business days after validated mapping (`partial`, operational target).

## Policy Note

Square/REST normalization depth is deferred in the current priority cycle (`partial`).
