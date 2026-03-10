# ShelfOps Business Demo Script

## Purpose
This is the full business-side teleprompter script for a prerecorded ShelfOps demo.

Use this file if you want to complete the entire business walkthrough without switching to any other demo doc. It includes:
- preflight
- exact page order
- what to click
- what to say while clicking
- why each product choice matters in business terms
- sourced market framing for why the product is worth building

Use this for:
- recruiters
- general hiring managers
- SMB owners
- pilot conversations
- non-technical stakeholders

## Recording Goal
By the end of this recording, the viewer should believe:
1. you understand the retail problem from lived operating experience
2. the product solves a real workflow, not just a reporting problem
3. ShelfOps is designed for a whole internal team, not one hypothetical user
4. the system is practical for SMB retailers while still reflecting enterprise-grade engineering judgment

## Preflight

### Runtime Prep
Run this before recording:

```bash
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
```

Optional read-only proof:

```bash
PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py
```

### Open Windows
Have these ready before you start:
- browser on `http://localhost:3000`
- terminal window ready for API proof
- optional second browser tab on the ML Ops or Operations page if you want to jump there quickly at the end

### What This Script Assumes
- the runtime has already been seeded with deterministic demo state
- the dashboard, alerts, forecasts, and purchase-order surfaces are populated
- you are recording this, so do not pause for questions

## Business Context You Can Quote
Use one or two of these numbers in the opening. Do not read all of them mechanically.

- [AlixPartners](https://www.alixpartners.com/insights/102kb3j/2024-holiday-shopping-outlook-what-consumers-really-want-and-how-retailers-can-de/) reported that **66% of consumers would likely shop somewhere else if the product they want is out of stock**.
- [PwC](https://www.pwc.com/gx/en/issues/c-suite-insights/voice-of-the-consumer-survey/product-availability.html) found that **product availability is the biggest factor affecting the in-store shopping experience**.
- [IHL Group](https://www.ihlservices.com/news/inventory-distortion-global-cost-retailers/) estimated that **inventory distortion costs retailers more than $1.7 trillion globally**.

Use them naturally, for example:
- "That is why inventory is not just an operations problem. It directly shapes whether the customer buys at all."
- "I built this because stockouts, overstocks, and bad purchasing decisions create real revenue leakage."

## Full Teleprompter Script

### 0. Opening Frame
**Action**
- Start on the main dashboard
- Keep the top KPI cards visible

**Say**
"ShelfOps is an inventory intelligence platform for smaller retailers that still manage inventory through spreadsheets, visual checks, and disconnected tools. I built it from direct retail experience after spending more than four years in retail operations and seeing the same problems repeatedly: stockouts, ghost inventory, reactive ordering, receiving mistakes, and buyers needing to override bad replenishment decisions."

"The reason this problem matters is that inventory issues are not just annoying internal workflow problems. They affect whether customers buy at all. AlixPartners reported that 66 percent of consumers are likely to shop somewhere else if the item they want is out of stock, and PwC found that product availability is the biggest factor shaping the in-store experience."

"So the purpose of ShelfOps is to help smaller retailers move from gut-feel inventory management to a more disciplined, auditable workflow without taking humans out of the loop."

**Why this section matters**
- establishes lived retail knowledge
- anchors the product in a real commercial problem
- keeps the conversation business-first before showing technical depth

### 1. Dashboard: The Shared Operating Surface
**Action**
- Stay on the dashboard
- Move the cursor slowly over:
  - KPI cards
  - active stores panel
  - model performance timeline
  - platform activity feed
  - system events panel

**Say**
"This dashboard is the shared operating surface. I designed it this way because not everyone inside a company needs the same level of detail, but they still need a common starting point."

"At the top, the KPI cards answer the immediate business question: what needs attention now? Open alerts, stock health, stockout rate, and forecast accuracy give leadership or a store operator a fast snapshot of current risk."

"Below that, I included active stores, model performance timeline, platform activity, and system events because I wanted the product to work for a real internal team, not just for one user persona."

"An executive or general manager might mostly care about the high-level health view. A team lead might care more about recent operational activity. A technical owner can use this as a bridge into the deeper control pages."

"That is a deliberate product decision. A lot of tools try to make one screen do everything for everyone. I wanted a shared surface, but still wanted each deeper page to serve a more specific role."

### 2. Alerts: Turn Signals Into Action
**Action**
- Click `Alerts` in the navigation
- Land on the open alerts tab
- Point to one anomaly-backed alert
- Point to acknowledge, resolve, and dismiss actions

**Say**
"This page is one of the most important workflow choices in the product. Retail teams do not need more passive dashboards. They need a triage queue."

"So instead of burying issues in charts, ShelfOps turns inventory risk, operational issues, and anomaly-driven events into something a human can review and act on."

"You can see that I kept the response options human-centered: acknowledge, resolve, or dismiss. I did that on purpose because high-impact inventory decisions should not silently automate themselves just because a model produced a score."

"This is also where anomaly detection becomes useful in practice. An anomaly is only valuable if it lands in the same operating flow where someone can review it and decide whether the issue is real, urgent, or just noise."

"So the product is not just surfacing data. It is structuring action."

### 3. Inventory: Replace Fragmented Spreadsheet Work
**Action**
- Click `Inventory`
- Show the KPI cards
- Toggle one filter if helpful
- Scroll the stock posture table

**Say**
"This page is the core operational inventory workspace. It is designed to replace a lot of the fragmented spreadsheet behavior that smaller retailers still rely on."

"The filters make it possible to move quickly by store, category, or inventory posture. The table is intentionally practical. It shows where stock is healthy, where reorder attention is needed, and where the system sees a risk condition."

"This is the page an inventory lead or buyer would spend much more time in than an executive would. That is another important product decision in the platform: role depth should increase as the job becomes more operational."

"For SMB teams, this kind of page matters because they usually do not have a separate planning system, a dedicated inventory analytics team, and a clean ERP workflow. They need one place to work."

### 4. Forecasts: Prediction Only Matters If It Improves Decisions
**Action**
- Click `Forecasts`
- Show the demand trend
- Show the category distribution
- Scroll to top demand products
- If the SHAP view is visible, highlight it briefly

**Say**
"This is where the predictive layer becomes visible, but I do not present the forecast as the product by itself. A forecast only matters if it improves a business decision."

"The demand trend and category views are there to help a buyer or planner understand where pressure is building. The top products view gives a quick sense of what matters most. And when the explainability layer is visible, it helps answer an important trust question: why does the system think demand is moving this way?"

"For this prerecorded demo, that per-forecast explanation view is a deterministic contribution estimate so the walkthrough stays repeatable. I present it as a trust aid, not as a claim that every visible contribution came from a live production explainer."

"I included that because inventory teams should not have to trust a black box on faith. Even in a business-oriented demo, I want to show that the product is trying to make the recommendation legible, not magical."

"The larger point is that the forecast is there to influence buying earlier, not just to decorate a chart."

### 5. Integrations: Start Simple, Architect Bigger
**Action**
- Click `Integrations`
- Highlight Square as the active SMB path
- Point to the non-active roadmap providers without overselling them

**Say**
"This page shows an important product and architecture distinction."

"For an SMB pilot, I would start with the simplest practical onboarding path, which is Square or CSV-based data flow."

"At the same time, I intentionally designed the backend to support broader enterprise-style integration patterns because I wanted the project to prove scale thinking, not just demo wiring."

"So the truthful framing is this: the near-term product path is simple and realistic for smaller retailers, while the architecture demonstrates that I know how to design for deeper integration environments."

"That is what I mean when I say this is a product for SMB and a project for enterprise."

### 6. Human-in-the-Loop Purchase Decisions
**Action**
- Keep the browser open on the product
- Switch to terminal
- Run:

```bash
curl -s http://localhost:8000/api/v1/purchase-orders/suggested | jq
cat docs/productization_artifacts/demo_runtime/demo_runtime_summary.json | jq
```

If you want to continue with an approve or reject example:

```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/approve" \
  -H "Content-Type: application/json" \
  -d '{}'
```

```bash
curl -s -X POST "http://localhost:8000/api/v1/purchase-orders/<PO_ID>/reject" \
  -H "Content-Type: application/json" \
  -d '{"reason_code":"forecast_disagree","notes":"Demo rejection path"}'
```

**Say**
"This is the bridge between AI and operations."

"The system can suggest purchase orders, but it does not silently take control away from the operator. A human can approve, edit, or reject the decision."

"That matters because in real retail operations, the right decision is not driven by forecast alone. It also depends on supplier timing, budget, shelf space, promotions, local context, and simple operator judgment."

"So I made human review a core product feature, not a missing capability."

"I also log those decisions because if a buyer repeatedly edits or rejects recommendations for the same reason, that becomes useful feedback for later policy or model improvement."

"This is one of the most important design choices in the whole platform: automate detection and recommendation, but keep high-impact decisions human-controlled."

### 7. Team Personas: Why the Product Has Multiple Pages
**Action**
- Click back across:
  - Dashboard
  - Alerts
  - Inventory
  - Forecasts
  - briefly `Operations`
  - do not spend long on `ML Ops`

**Say**
"One thing I wanted to do clearly in the product design is acknowledge that different internal users need different views."

"A stakeholder or owner may mostly live on the dashboard."

"A buyer or inventory manager is more likely to live in alerts, inventory, and forecasts."

"A technical operator or internal data owner may use operations and MLOps."

"That is why the product is broader than a single dashboard page. It is meant to support a real team structure inside a company."

"The reason I keep saying that is because I wanted this product to feel operationally believable. Not everybody in a real business would ever touch the MLOps page, and that is exactly the point."

### 8. Close: Today, Pilot Next, Later
**Action**
- End on the dashboard or operations page
- Keep the cursor still for the close

**Say**
"Today, what is live and truthful is an end-to-end workflow: visibility, alerts, forecasts, anomaly-backed operational signals, and human-reviewed purchase decisions."

"Pilot next means tightening operator visibility, integration resilience, and release confidence for a first Square or CSV-first SMB rollout."

"Later is broader enterprise hardening and deeper model sophistication, but I do not claim those pieces are fully production-ready today."

"What I wanted this walkthrough to show is that I understand the retail problem, I understand the users inside the business, and I built the product around practical inventory decisions rather than generic AI theater."

"If you have any questions, please feel free to contact me. I would be glad to answer them."

## Fallback Lines
- "The point of this page is not more data, it is faster decision quality."
- "I built the architecture bigger than the buyer workflow because strong systems let the customer experience stay simple."
- "This is decision support, not black-box automation."

## Truth Boundaries
- Do not claim real-time streaming everywhere.
- Do not claim autonomous ordering.
- Do not claim enterprise GA readiness.
- Do say the platform demonstrates enterprise-grade patterns.
- Do say the MLOps business metrics in demo mode are modeled estimates from seeded evidence.
