# ShelfOps Backend

## Data Validation Utilities

```bash
# Validate multi-dataset training readiness and write a markdown report
python scripts/validate_training_datasets.py

# Validate a tenant contract profile against sample source data
python scripts/validate_customer_contract.py \
  --contract ../contracts/demo_smb/smb_csv/v1.yaml \
  --sample-path tests/fixtures/contracts/sample_smb.csv

# Run SMB onboarding flow (map -> validate -> canonicalize -> train candidate)
python scripts/run_onboarding_flow.py \
  --contract ../contracts/demo_smb/smb_csv/v1.yaml \
  --sample-path tests/fixtures/contracts/sample_smb.csv

# Generate model performance decision log (champion/challenger history)
python scripts/generate_model_performance_log.py
```

Default output:

- `docs/DATASET_VALIDATION_REPORT.md`
- `docs/MODEL_PERFORMANCE_LOG.md`
- `backend/reports/contract_validation_report.json`
- `backend/reports/contract_validation_report.md`

This check validates canonical training-data contract readiness for:

- Favorita
- Walmart
- Rossmann
- Synthetic seed transactions

It is designed for model training/evaluation readiness, not live dashboard catalog population.

`docs/MODEL_PERFORMANCE_LOG.md` is also auto-refreshed whenever a model is registered via `ml.experiment.register_model(...)`.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Seed test data
python scripts/seed_test_data.py

# Start development server
uvicorn api.main:app --reload
```
