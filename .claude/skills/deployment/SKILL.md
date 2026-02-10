# Deployment Skill

**Purpose**: Deploy ShelfOps to Google Cloud Platform  
**When to use**: Containerization, Cloud Run deployment, CI/CD, environment management

---

## Core Patterns

### 1. Dockerfile (Backend)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Run with Uvicorn
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 2. Docker Compose (Local Dev)

```yaml
version: '3.8'
services:
  db:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_DB: shelfops
      POSTGRES_USER: shelfops
      POSTGRES_PASSWORD: dev_password
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [db, redis]
    env_file: .env
    volumes: ["./backend:/app"]
    command: uvicorn api.main:app --host 0.0.0.0 --reload

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [api]
    volumes: ["./frontend:/app"]

volumes:
  pgdata:
```

### 3. Cloud Run Deployment

```bash
# Build and push
gcloud builds submit --tag gcr.io/$PROJECT_ID/shelfops-api ./backend

# Deploy
gcloud run deploy shelfops-api \
  --image gcr.io/$PROJECT_ID/shelfops-api \
  --platform managed \
  --region us-central1 \
  --set-env-vars DATABASE_URL=$DB_URL,REDIS_URL=$REDIS_URL \
  --min-instances 1 \
  --max-instances 10 \
  --memory 1Gi \
  --cpu 2
```

### 4. GitHub Actions CI/CD

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r backend/requirements.txt
      - run: cd backend && pytest tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: gcloud builds submit --tag gcr.io/${{ vars.PROJECT_ID }}/shelfops-api ./backend
      - run: gcloud run deploy shelfops-api --image gcr.io/${{ vars.PROJECT_ID }}/shelfops-api --region us-central1
```

---

## DO / DON'T

### DO
- ✅ Use multi-stage Docker builds (smaller images)
- ✅ Use `.dockerignore` (exclude tests, docs, node_modules)
- ✅ Use Secret Manager for sensitive env vars
- ✅ Set `min-instances: 1` to avoid cold starts
- ✅ Run tests before deploying (CI/CD gate)

### DON'T
- ❌ Hardcode secrets in Dockerfiles or CI configs
- ❌ Deploy without running tests
- ❌ Use `latest` tag (use commit SHA or version)
- ❌ Skip health checks (Cloud Run needs `/health`)

---

**Last Updated**: 2026-02-09
