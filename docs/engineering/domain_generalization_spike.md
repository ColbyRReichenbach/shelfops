# ShelfOps — Research Spike: Domain Generalization & Vertical Expansion

- Last verified date: March 10, 2026
- Audience: builders and strategy reviewers
- Scope: research spike for possible future vertical expansion
- Author: Strategy thread, February 24, 2026
- Status: **Open research spike — not an implementation or current product commitment**
- Source of truth: current product scope remains the active docs and codebase, not this spike
- Time-box: 1–2 days
- Prerequisite reading: `docs/BRAINSTORM.md §20`, `backend/ml/features.py`, `backend/inventory/optimizer.py`

---

## Why This Spike Exists

ShelfOps' ML pipeline and business logic encode retail-specific assumptions at every layer —
EOQ/ROP formulas, feature engineering windows, Pandera schema bounds, and LSTM temporal
patterns are all calibrated for retail POS cadence. Expanding to adjacent verticals (food
service, specialty/boutique, light manufacturing) without understanding how to generalize these
assumptions would either require a parallel codebase per vertical or produce models that simply
perform poorly outside retail.

This spike exists to answer the research questions in BRAINSTORM.md §20 before any
architectural decision is made. It is **not an implementation**. The output is a structured
finding document that enables a go/no-go decision and, if go, identifies the right architectural
decision points.

---

## Research Questions

### Q1 — How do production multi-vertical inventory platforms handle domain generalization?

**Target companies**: Relex Solutions, Blue Yonder (JDA), o9 Solutions, Toolio, Slim4 (Slimstock), Flowspace.

For each, try to answer:
- Do they ship one ML model with per-vertical configuration, or separate vertical products sharing infrastructure?
- What is the configuration surface exposed to customers? Rule-based presets? Consultant-parameterized? Customer self-serve?
- How do they handle vertical-specific demand distributions (e.g., heavy-tail restaurant ingredients vs. normal retail)?
- Are there published case studies, conference talks (NeurIPS, KDD, ICML applied tracks), or engineering blog posts describing the internals?

**Sources to check**:
- Company engineering blogs (Relex Labs, Blue Yonder engineering blog)
- Google Scholar: "multi-vertical inventory optimization", "demand forecasting domain adaptation retail"
- LinkedIn posts / talks from DS leads at these companies
- Patent filings (USPTO, Espacenet) — Blue Yonder has filed on forecasting architecture

**Expected output**: A short table: company × approach (one of: presets / config / separate models / unknown).

---

### Q2 — Does LLM-assisted ML pipeline configuration exist in production?

The hypothesis in BRAINSTORM.md §20.3 is that an LLM could generate a domain config object
at onboarding time (feature presets, seasonality windows, Pandera bounds, lead time priors)
based on a business description questionnaire. This is adjacent to but distinct from AutoML.

**Questions**:
- Has this been done in production? Search for: "LLM pipeline configuration", "LLM AutoML", "LLM-assisted feature engineering configuration", "prompt-driven ML pipeline"
- What are the closest published approaches? (AutoML with domain priors, FLAML + context, etc.)
- What are the known failure modes of LLM-generated configuration for numerical ML pipelines?
  - Hallucinated ranges, inconsistent units, over-confident priors
- Is there a published evaluation framework for LLM-generated ML configs?

**Sources to check**:
- arXiv (cs.LG, cs.AI): 2024–2026 papers on LLM + AutoML, LLM + feature engineering
- NeurIPS / ICML 2024–2025 proceedings
- LangChain / LlamaIndex ecosystem — any production patterns for LLM → structured config output
- Hugging Face blog, Towards Data Science for applied implementations

**Expected output**: Verdict — novel / partially explored / well-covered. If well-covered, identify
the closest existing approach and whether it is usable off the shelf.

---

### Q3 — Few-shot and sparse demand forecasting for high-variance SKUs

Specialty/boutique retail and food service have demand distributions that break the assumptions
behind the current feature set: heavy-tail distributions, intermittent demand, very small SKU
populations per tenant.

**Questions**:
- What is the current state of the art for intermittent demand forecasting? (Croston's method,
  TSB, ADIDA, Neural Basis Expansion — NBEATS/N-HiTS adapted for sparse series)
- Is there a usable transfer learning approach: pretrain on a large retail dataset (Favorita,
  M5), fine-tune on a new vertical with <100 SKUs and <90 days of history?
- What feature engineering changes are required? (Time-of-day for food service, lot expiry
  for perishables, event calendars for boutique)
- At what history length / SKU count does standard XGBoost become competitive with
  intermittent demand methods?

**Sources to check**:
- Nixtla (StatsForecast / NeuralForecast) docs — they have explicit intermittent demand support
- M5 Accuracy and Uncertainty competition papers (2020) — many intermittent demand results
- arXiv: "zero-shot forecasting", "few-shot time series", "intermittent demand neural"
- Kaggle competition notebooks for Favorita and M5 with sparse-SKU approaches

**Expected output**: A ranked list of candidate approaches for sparse demand forecasting,
with notes on implementation complexity relative to the current XGBoost/LSTM stack.

---

### Q4 — At what scale does clustering-based prior discovery become meaningful?

BRAINSTORM.md §20.5 proposes discovering vertical clusters empirically from SHAP importance
distributions across tenants rather than hardcoding them. This requires enough tenants to form
statistically stable clusters.

**Questions**:
- What is the minimum sample size for stable k-means / hierarchical clustering on
  high-dimensional feature importance vectors? (Rule-of-thumb: 5× the feature dimension, but
  what do practitioners actually observe?)
- Has tenant clustering for ML prior initialization been done in SaaS ML platforms?
  Check: Sagemaker, Azure ML documentation and whitepapers.
- Is there a simpler intermediate approach — e.g., two manually curated cluster centroids
  (retail vs. food service) that get replaced by discovered centroids once enough tenants exist?
- What metadata features (beyond SHAP) are most predictive of which cluster a new tenant
  belongs to? (stated business type, SKU count, demand variance, lead time distribution)

**Sources to check**:
- Federated learning / multi-task learning literature for SaaS ML platforms
- "Meta-learning for time series forecasting" — arXiv, NeurIPS
- Practical write-ups on tenant personalization in B2B SaaS ML (Amplitude, Mixpanel, etc.)

**Expected output**: Minimum tenant count estimate (with reasoning) before clustering is
trustworthy. A proposed fallback strategy for pre-cluster scale.

---

## Spike Execution Plan

### Day 1 — Competitive & Applied Research (Q1, Q2)

| Hour | Task |
|---|---|
| 0–1 | Set up a research notes scratch doc. Skim Relex, Blue Yonder, o9 engineering blogs and LinkedIn for architecture signals. |
| 1–2 | USPTO / Espacenet patent search: Blue Yonder + demand forecasting. arXiv search: LLM + AutoML + pipeline configuration (2024–2026). |
| 2–3 | Deep-read 2–3 most relevant papers or blog posts from Q1/Q2 search. |
| 3–4 | Synthesize Q1 and Q2 findings into the output tables. |

### Day 2 — ML Research (Q3, Q4) + Synthesis

| Hour | Task |
|---|---|
| 0–1 | Nixtla StatsForecast/NeuralForecast docs for intermittent demand. M5 competition papers for sparse-SKU results. |
| 1–2 | arXiv: zero-shot / few-shot forecasting, transfer learning for time series. |
| 2–3 | Q4 research: clustering literature, federated/multi-task learning, minimum sample size. |
| 3–4 | Write the findings document. Fill in go/no-go criteria. Identify architectural decision points. |

---

## Definition of Done

The spike is complete when a `docs/engineering/domain_generalization_findings.md` file exists
and contains all of the following:

- [ ] Q1 table: company × generalization approach (at least 4 companies evaluated)
- [ ] Q2 verdict: novel / partially explored / well-covered, with the closest existing approach named
- [ ] Q3 ranked list: ≥3 candidate approaches for sparse/intermittent demand forecasting with complexity notes
- [ ] Q4 estimate: minimum tenant count for stable clustering, with reasoning and fallback strategy
- [ ] Go/no-go recommendation with explicit criteria (see below)
- [ ] If go: list of architectural decision points that must be resolved before §20.3 is specced

---

## Go / No-Go Criteria

### Go (proceed to architecture spec for §20.3)

All of the following must be true:
- Q2 finds no off-the-shelf solution that covers ≥80% of the use case — confirms the approach is not reinventing an existing tool
- Q3 finds at least one sparse demand approach that can run within the current XGBoost training infrastructure without a full pipeline rewrite
- Q4 finds a credible fallback strategy for pre-cluster scale (i.e., we don't need 500 tenants before the system is useful)
- No competitive finding in Q1 reveals that a dominant player already executes this approach well enough to make it a non-differentiator

### No-Go (defer indefinitely or abandon)

Any of the following:
- Q2 finds a mature, open-source, off-the-shelf solution — evaluate adopting it rather than building
- Q3 finds no viable sparse demand approach compatible with the current stack — vertical expansion requires a deeper ML rearchitecture first
- Q1 reveals that all serious players use manually curated vertical presets (consultant-parameterized) — the LLM approach may not be worth the complexity vs. just building a good preset library

---

## Out of Scope for This Spike

- Implementation of any kind
- Changes to `features.py`, `optimizer.py`, or any model training code
- Designing the LLM prompt or domain config schema (that is the output of the architecture spec, which comes after this spike)
- Evaluating specific LLM models or providers
- Any frontend or API design

---

## Files to Create

| File | Description |
|---|---|
| `docs/engineering/domain_generalization_spike.md` | This document — the spike plan |
| `docs/engineering/domain_generalization_findings.md` | Created during spike execution — findings and recommendation |

No existing files are modified by this spike.

---

## Complexity Estimate

**S — 1–2 days of focused research.** No code changes. The bottleneck is access to
non-public information about how Relex/Blue Yonder implement their internals; expect
to work from indirect signals (patents, blog posts, conference talks, job postings).
