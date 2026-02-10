# ShelfOps - Complete Claude Code Structure

**Last Updated**: 2026-02-10  
**Status**: Production-ready, comprehensive

---

## Overview

This Claude Code project contains everything needed to build ShelfOps, a retail inventory intelligence platform, following Anthropic's best practices.

**Total Components**:
- ✅ 7 Skills (specialized knowledge domains)
- ✅ 3 Agents (role-based AI assistants)
- ✅ 7 Workflows (step-by-step guides)
- ✅ Learning system (error tracking, solutions)

---

## Skills (7 Total)

**Skills** = Specialized knowledge domains referenced by agents

### 1. postgresql/ - Database & Time-Series
**Size**: 14KB (comprehensive)  
**Purpose**: PostgreSQL + TimescaleDB for retail data  
**Covers**: Schema design, migrations, indexing, query optimization, multi-tenant, hypertables  
**When**: Database design, data modeling, performance tuning

### 2. api-integration/ - External System Connections
**Size**: 17KB (comprehensive)  
**Purpose**: Integrate with Square, Shopify, NetSuite, EDI X12, SFTP, Kafka  
**Covers**: OAuth 2.0, webhooks, rate limiting, circuit breakers, EDI parsing, adapter pattern  
**When**: Connecting POS, ERP, WMS, or enterprise retailer systems

### 3. ml-forecasting/ - Demand Forecasting + MLOps
**Size**: 14KB (comprehensive)  
**Purpose**: Build LSTM + XGBoost ensemble with MLOps standards  
**Covers**: Two-phase feature engineering (27 cold-start / 46 production), model training, MLflow experiment tracking, SHAP explainability, Pandera validation, Plotly charts, model registry  
**When**: Training ML models, improving forecast accuracy, analyzing model behavior

### 4. fastapi/ - REST API Development
**Size**: Compact reference  
**Purpose**: Build production FastAPI endpoints  
**When**: Creating new API endpoints

### 5. react-dashboard/ - Frontend UI
**Size**: Compact reference  
**Purpose**: Build React dashboards with TypeScript + Tailwind  
**When**: Creating dashboard components

### 6. alert-systems/ - Real-Time Notifications
**Size**: Compact reference  
**Purpose**: Redis pub/sub + WebSocket + Email alerts  
**When**: Implementing alert delivery

### 7. deployment/ - Production Deployment
**Size**: Compact reference  
**Purpose**: Deploy to Google Cloud Platform  
**When**: Deploying to production

---

## Agents (3 Total)

**Agents** = Role-based AI assistants with specific responsibilities

### 1. data-engineer/
**Skills**: postgresql, api-integration  
**Responsibilities**:
- Database schema design and migrations
- Data pipeline development (POS → database)
- Data quality validation
- Query optimization
- TimescaleDB management

**When to use**: Database work, ETL pipelines, data integrations

### 2. ml-engineer/
**Skills**: ml-forecasting  
**Responsibilities**:
- Feature engineering (two-phase: 27 cold-start → 46 production)
- Model training (LSTM + XGBoost ensemble, 65/35 weights)
- Model evaluation (MAE, MAPE targets with time-series CV)
- MLflow experiment tracking (log every run)
- SHAP explanations (generate per version)
- Data validation (Pandera gates before training)
- Model registry management (champion/challenger)
- Performance monitoring, weekly retraining

**When to use**: ML model development, forecast accuracy, explainability, MLOps

### 3. full-stack-engineer/
**Skills**: fastapi, react-dashboard, alert-systems  
**Responsibilities**:
- FastAPI REST endpoints
- React dashboard components
- Real-time alerts (WebSocket)
- User authentication

**When to use**: API development, UI work, frontend features

---

## Workflows (7 Total)

**Workflows** = Step-by-step guides for completing specific tasks

Aligned with 8-week MVP roadmap:

### Week 1: Database Setup
**1. setup-database.md**
- Initialize PostgreSQL + TimescaleDB
- Run migrations (16 tables including edi_transaction_log)
- Create hypertables, indexes
- Seed test data

### Week 2: Integrations
**2. integrate-pos-system.md**
- Implement OAuth flow (Square/Shopify)
- Set up webhooks
- Map external schema to ShelfOps
- Test integration

**3. integrate-enterprise-data.md** *(NEW)*
- Configure EDI X12, SFTP, or Kafka adapter
- Test connection and initial sync
- Set up Celery scheduled sync
- Generate test data with seed scripts
- Verify GTINs and EDI audit log

### Week 3-4: ML Models + MLOps
**4. train-forecast-model.md**
- Prepare training data (Kaggle: Favorita/Walmart/Rossmann)
- Feature engineering (two-phase: 27 cold-start / 46 production)
- Train LSTM + XGBoost ensemble
- MLflow tracks params, metrics, artifacts per run
- SHAP generates global + local explanations
- Pandera validates data at 3 pipeline gates
- Register model in registry, promote if MAE improves
- Schedule weekly retraining (Celery cron)

### Week 5-6: Dashboard
**5. build-dashboard.md**
- Set up React project
- Implement Auth0
- Build core components (Alerts, Charts)
- Connect to API, WebSocket

### Week 7: Production Deployment
**6. deploy-to-production.md**
- Build Docker image
- Push to GCR
- Deploy to Cloud Run
- Configure CI/CD (GitHub Actions)

### Week 8: Customer Onboarding
**7. onboard-customer.md**
- Create customer account
- Import stores, products
- Connect POS system
- Run initial forecasts

---

## Learning System

**Purpose**: Self-improving through error tracking

### Components
- **hooks/on_error.py** - Logs errors to errors.md
- **hooks/on_success.py** - Logs solutions to solutions.md
- **docs/errors.md** - Historical error log
- **docs/solutions.md** - Known solutions

**How it works**:
1. Error occurs → on_error.py logs it
2. Error resolved → on_success.py logs solution
3. Future similar errors → check solutions.md first

---

## Project Structure

```
.claude/
├── CLAUDE.md              # Main project context
├── STRUCTURE.md          # This file
├── settings.json         # Claude Code configuration
├── skills/               # 7 specialized knowledge domains
│   ├── postgresql/
│   ├── api-integration/
│   ├── ml-forecasting/
│   ├── fastapi/
│   ├── react-dashboard/
│   ├── alert-systems/
│   └── deployment/
├── agents/               # 3 role-based assistants
│   ├── data-engineer/
│   ├── ml-engineer/
│   └── full-stack-engineer/
├── workflows/            # 7 step-by-step guides
│   ├── setup-database.md
│   ├── integrate-pos-system.md
│   ├── integrate-enterprise-data.md  # NEW
│   ├── train-forecast-model.md
│   ├── build-dashboard.md
│   ├── deploy-to-production.md
│   └── onboard-customer.md
├── hooks/                # Learning system hooks
│   ├── on_error.py
│   └── on_success.py
└── docs/                 # Learning system logs
    ├── errors.md
    └── solutions.md
```

---

## How to Use This Structure

### For a Specific Task

1. **Identify the task type** (database, ML, API, UI, deployment)
2. **Choose the right agent** based on responsibilities
3. **Agent reads relevant skills** before starting work
4. **Follow the workflow** if there's a matching one

### Example: "Add a new table to store customer feedback"

**Steps**:
1. Use **data-engineer** agent (database work)
2. Agent reads **postgresql** skill (schema design patterns)
3. Agent creates migration following skill best practices
4. Agent tests migration before production

### Example: "Improve forecast accuracy for seasonal items"

**Steps**:
1. Use **ml-engineer** agent (ML model work)
2. Agent reads **ml-forecasting** skill (feature engineering, training)
3. Agent adds seasonality features
4. Agent follows **train-forecast-model** workflow
5. Agent evaluates improvement, deploys if better

### Example: "Build new alert type for overstock"

**Steps**:
1. Use **full-stack-engineer** agent (API + UI)
2. Agent reads **fastapi** skill (API patterns)
3. Agent reads **alert-systems** skill (notification patterns)
4. Agent creates API endpoint + dashboard component

---

## Alignment with Product Roadmap

This structure directly supports the 8-week MVP roadmap:

| Week | Focus | Workflow | Agent | Skills |
|------|-------|----------|-------|--------|
| 1-2 | Foundation | setup-database, integrate-pos-system, integrate-enterprise-data | data-engineer | postgresql, api-integration |
| 3-4 | Analytics | train-forecast-model | ml-engineer | ml-forecasting |
| 5-6 | Dashboard | build-dashboard | full-stack-engineer | fastapi, react-dashboard, alert-systems |
| 7 | Deployment | deploy-to-production | full-stack-engineer | deployment |
| 8 | Pilot | onboard-customer | data-engineer | postgresql, api-integration |

---

## Quality Standards

All components follow Anthropic's best practices:

**Skills**:
- ✅ Clear purpose statement
- ✅ Code examples (not just theory)
- ✅ DO/DON'T sections
- ✅ Best practices from industry

**Agents**:
- ✅ Clear role definition
- ✅ Specific responsibilities
- ✅ Decision guidelines
- ✅ Communication style

**Workflows**:
- ✅ Step-by-step instructions
- ✅ Prerequisites listed
- ✅ Checklists for verification
- ✅ Troubleshooting section

---

## Future Enhancements

**Planned additions**:
- Additional skills: security, monitoring, testing
- More workflows: incident response, performance tuning
- Enhanced learning system: pattern recognition, auto-suggestions
- MLOps monitoring: MLflow model drift detection, automated retraining triggers

**As project grows**:
- Skills get updated with new patterns
- Agents gain more specialized knowledge
- Workflows expand with lessons learned

---

## For Hiring Managers

**What this demonstrates**:

1. **Systematic Thinking**: Organized structure aligned with product roadmap
2. **Best Practices**: Follows Anthropic's official guidance
3. **Production-Ready**: Not toy examples, real patterns from industry
4. **Self-Improving**: Learning system captures institutional knowledge
5. **Comprehensive**: 7 skills + 3 agents + 6 workflows = complete coverage

**This is NOT just documentation** - it's a complete AI-assisted development framework that would accelerate any engineer building ShelfOps.

---

**Ready to build!** 🚀
