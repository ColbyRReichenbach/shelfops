# Workflow: CI/CD Setup and GCP Deployment

**Purpose**: Configure GitHub Actions CI with deploy job, deploy to GCP Cloud Run
**Agent**: devops-engineer
**Duration**: 3-5 hours

## Prerequisites

- Phase 3 (Testing & Quality) complete — all tests passing
- GCP project created, billing enabled
- `gcloud` CLI authenticated locally
- GitHub secrets added: `GCP_SA_KEY`, `DATABASE_URL`, `REDIS_URL`

---

## Step 1: Verify Existing CI

The CI pipeline exists at `.github/workflows/ci.yml`.
Current jobs: `backend-lint`, `backend-test`, `frontend-lint`, `frontend-build`.

Push a test branch and verify all jobs pass before proceeding.

---

## Step 2: Update Python Version in CI

The pipeline may reference Python 3.10. Update to 3.11:

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
```

---

## Step 3: GCP Setup

```bash
gcloud config set project shelfops-prod
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com sqladmin.googleapis.com

gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions CI/CD"

gcloud projects add-iam-policy-binding shelfops-prod \
  --member="serviceAccount:github-actions@shelfops-prod.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud iam service-accounts keys create key.json \
  --iam-account=github-actions@shelfops-prod.iam.gserviceaccount.com
# Add key.json content to GitHub secret: GCP_SA_KEY
```

---

## Step 4: Add Deploy Job to CI

Add to `.github/workflows/ci.yml` (triggers on `main` push only):

```yaml
deploy:
  name: Deploy to Cloud Run
  runs-on: ubuntu-latest
  needs: [backend-test, frontend-build]
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  steps:
    - uses: actions/checkout@v4
    - uses: google-github-actions/auth@v2
      with:
        credentials_json: ${{ secrets.GCP_SA_KEY }}
    - uses: google-github-actions/setup-gcloud@v2
    - name: Build and push API image
      run: |
        gcloud builds submit \
          --tag gcr.io/shelfops-prod/api:${{ github.sha }} \
          --file Dockerfile .
    - name: Deploy API to Cloud Run
      run: |
        gcloud run deploy shelfops-api \
          --image gcr.io/shelfops-prod/api:${{ github.sha }} \
          --platform managed \
          --region us-central1 \
          --set-env-vars DATABASE_URL=${{ secrets.DATABASE_URL }} \
          --set-env-vars REDIS_URL=${{ secrets.REDIS_URL }} \
          --min-instances 1 \
          --max-instances 10 \
          --allow-unauthenticated
```

---

## Step 5: Cloud SQL

```bash
gcloud sql instances create shelfops-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

gcloud sql databases create shelfops --instance=shelfops-db

# Run migrations against Cloud SQL
PYTHONPATH=backend DATABASE_URL="postgresql+asyncpg://..." alembic upgrade head
```

---

## Step 6: Smoke Test

```bash
BASE_URL="https://shelfops-api-xxxxx-uc.a.run.app"
curl $BASE_URL/health
curl -H "Authorization: Bearer $TOKEN" $BASE_URL/api/v1/stores/
```

---

## Checklist

- [ ] All CI jobs pass on `main`
- [ ] Python version updated to 3.11 in ci.yml
- [ ] GCP project APIs enabled
- [ ] Service account created with `roles/run.admin`
- [ ] `GCP_SA_KEY`, `DATABASE_URL`, `REDIS_URL` in GitHub secrets
- [ ] Deploy job added (triggers on `main` push only)
- [ ] Docker build succeeds via `gcloud builds submit`
- [ ] Cloud Run service deployed — health check returns 200
- [ ] Cloud SQL created and migrations applied
