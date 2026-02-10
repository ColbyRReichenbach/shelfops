# Workflow: Deploy to Production

**Purpose**: Deploy ShelfOps to Google Cloud Platform

**Agent**: full-stack-engineer

**Duration**: 4-6 hours

---

## Steps

### 1. Build Docker Image
```dockerfile
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0"]
```

### 2. Push to Google Container Registry
```bash
gcloud builds submit --tag gcr.io/shelfops-prod/api
```

### 3. Deploy to Cloud Run
```bash
gcloud run deploy shelfops-api \
  --image gcr.io/shelfops-prod/api \
  --platform managed \
  --region us-central1 \
  --set-env-vars DATABASE_URL=$DB_URL \
  --min-instances 1 --max-instances 10
```

### 4. Configure CI/CD (GitHub Actions)
```yaml
on: push
jobs:
  deploy:
    steps:
      - uses: actions/checkout@v3
      - run: gcloud builds submit
      - run: gcloud run deploy
```

---

**Checklist**:
- [ ] Docker image built
- [ ] Pushed to GCR
- [ ] Deployed to Cloud Run
- [ ] Environment variables set
- [ ] CI/CD configured
- [ ] Health check passing

**Last Updated**: 2026-02-09
