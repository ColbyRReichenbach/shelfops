# ShelfOps Business Walkthrough

## Audience
Use this walkthrough for:
- recruiters
- non-technical hiring managers
- SMB owners
- pilot conversations

## Goal
Prove three things:
1. You understand the retail problem from direct experience.
2. ShelfOps is a usable inventory workflow, not just a model demo.
3. The product creates value for smaller retailers without removing human control.

## Core Framing
Use this early:

> ShelfOps is an inventory intelligence platform for smaller retailers that still operate manually or with fragmented tooling. It helps them move from gut-feel replenishment to auditable, data-backed decisions.

Then add:

> The short version is: product for SMB, project for enterprise.

## Runtime Prep
Before the walkthrough:

```bash
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
```

Optional proof check:

```bash
PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py
```

## Opening Hook
Use this structure in the first 60-90 seconds:

1. "A lot of smaller retailers still manage inventory with visual checks, spreadsheets, and reactive ordering."
2. "I spent 4+ years in retail, so I built this from real operating pain points I saw repeatedly."
3. "ShelfOps brings together inventory visibility, forecasts, alerts, and purchase-order decisions into one workflow."
4. "The goal is to reduce stockouts, reduce overstock, and make decisions traceable."

## Suggested Timing
1. 0:00-1:30 Hook + why you built it.
2. 1:30-6:30 Platform walkthrough.
3. 6:30-9:00 Human-in-the-loop purchase decisions.
4. 9:00-11:00 SMB value and pilot framing.
5. 11:00-12:00 Close and technical transition.

## Script

### 0:00-1:30 | Why This Exists
Say:
- "I built ShelfOps because smaller retailers often make inventory decisions manually, and that creates the same problems over and over: stockouts, overstock, and bad purchasing decisions."
- "I saw that firsthand over 4+ years in retail, so I wanted to build something that combines domain knowledge with automation instead of replacing operators with a black box."
- "This is meant to feel like intelligent inventory operations software, not just a forecasting model."

What to emphasize:
- lived retail knowledge
- operational pain, not abstract ML
- decisions matter more than raw predictions

### 1:30-6:30 | Platform Walkthrough
Open `http://localhost:3000`.

#### Dashboard
Say:
- "This is the operating snapshot. If I were managing inventory, this is where I would start the day."
- "I care less about pretty charts and more about what requires action now."

#### Alerts
Say:
- "Retail teams do not need more dashboards; they need a triage queue."
- "The system surfaces issues before they become missed sales or excess stock."

#### Inventory
Say:
- "This is the operational layer. It shows where inventory posture actually sits at the store and SKU level."
- "For SMBs, this replaces fragmented spreadsheets and reactive checks."

#### Forecasts
Say:
- "The forecast is useful only because it feeds decisions. A forecast by itself does not improve the business."
- "The point is to anticipate demand early enough to influence purchasing."

#### Integrations
Say:
- "Smaller retailers rarely have perfect systems. They usually have partial systems and disconnected data."
- "I built the platform so onboarding can start simple, but the backend still supports broader enterprise-style integrations."

### 6:30-9:00 | Human-in-the-Loop Purchase Decisions
Say:
- "One of the most important design choices here is that humans stay in control."
- "The system suggests orders, but a planner can approve, reject, or edit them with a reason."
- "That matters because retail decisions often depend on vendor timing, shelf capacity, budget, promotions, and local context that raw demand prediction does not fully capture."

Show:

```bash
curl -s http://localhost:8000/api/v1/purchase-orders/suggested | jq
cat docs/productization_artifacts/demo_runtime/demo_runtime_summary.json | jq
```

Suggested talk track:
- "This is the bridge between AI and operations."
- "I intentionally log reason codes because that creates a feedback loop for later model and policy improvement."

### 9:00-11:00 | Why This Matters to SMBs
Say:
- "If I were pitching this to a pilot customer, the value proposition is straightforward: less manual inventory work, better buying decisions, more visibility, and retained human control."
- "This is not positioned as replacing an ERP. It is positioned as giving smaller teams an intelligence layer they typically do not have."
- "The system helps them operate with more discipline without forcing enterprise complexity onto the buyer."

### 11:00-12:00 | Close
Say:
- "So the business story is simple: this turns inventory from reactive manual work into a more consistent, data-backed workflow."
- "The deeper technical story is where the platform becomes more interesting, because I built the backend and MLOps structure to operate like a much larger system."

Transition line:
- "If useful, I can now walk through how it was actually built and why I made those technical choices."

## Questions to Expect
- Why did you choose this problem?
- What makes this useful for a smaller retailer?
- How does this differ from spreadsheets or existing POS tools?
- Why keep humans in the loop?
- How would onboarding start for a real pilot?
