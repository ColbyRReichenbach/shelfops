# ShelfOps Retail + DS Story Draft

Working draft. Do not publish until the experiment numbers, screenshots, and
claim boundaries are filled from real ShelfOps runs.

## Core Story

I started learning retail inventory from the floor before I understood the
models behind it. At Target, inventory work was a constant feedback loop:
audits, shelf fills, backroom checks, suspect tasks, replenishment decisions,
and corrections when the system inventory did not match the shelf.

Later, as I studied data science and machine learning, I started recognizing the
logic behind those workflows. Forecasting was only one part of the problem. The
real operating question was:

> What should we do next, what tradeoff are we making, and how do we learn from
> the outcome?

ShelfOps came from that idea. It is an inventory decision and MLOps platform for
retail teams. It ingests operating data, trains demand and anomaly models,
generates replenishment recommendations, lets humans accept, edit, or reject
those decisions, records the outcome, and turns that evidence into governed
model and policy improvement.

The platform story is not just "I built a dashboard." The story is:

> I built a closed-loop retail ML system where forecasting, inventory decisions,
> human review, business outcomes, and governed model/policy improvement are
> connected in one reproducible workflow.

## Claim Boundary

Use these labels consistently:

- `benchmark`: public dataset evidence, such as M5/Walmart or FreshRetailNet.
- `simulated`: replay or policy simulation, not measured merchant impact.
- `provisional`: app walkthrough or incomplete outcome window.
- `measured`: only real merchant outcomes after observed feedback windows.
- `unavailable`: not enough evidence yet.

Do not claim measured merchant ROI until a real pilot exists.

## Source Material Placeholders

### Personal / Retail Photos

- `[PHOTO: Target-era inventory/backroom/shelf work photo, if available and appropriate]`
- `[PHOTO: personal workspace / notebook / model training screenshot]`
- `[PHOTO: ShelfOps dashboard screenshot: Replenishment Queue]`
- `[PHOTO: ShelfOps dashboard screenshot: Model Lab champion/challenger]`
- `[PHOTO: ShelfOps dashboard screenshot: experiment spec / audit trail]`

### Platform Screenshots

- `[SCREENSHOT: Data Readiness page showing current benchmark/pilot readiness]`
- `[SCREENSHOT: Product detail forecast chart with historical vs forecast series]`
- `[SCREENSHOT: Replenishment recommendation drawer with order cost, holding cost, spoilage risk]`
- `[SCREENSHOT: Model Lab showing demand forecast champion]`
- `[SCREENSHOT: Model Lab showing anomaly detector champion/challenger]`
- `[SCREENSHOT: Experiment Workbench showing materialized spec hash]`
- `[SCREENSHOT: Manual vs AI comparison report once created]`

### Experiment Numbers To Fill

- `[DATA: M5/Walmart benchmark subset description]`
- `[DATA: baseline/champion model version]`
- `[DATA: baseline WAPE, MASE, bias, interval coverage]`
- `[DATA: best manual challenger metrics]`
- `[DATA: manual challenger improvement percent]`
- `[DATA: manual decision replay metrics: simulated stockout exposure, overstock cost, order cost, service level]`
- `[DATA: best AI-assisted challenger metrics]`
- `[DATA: AI-assisted challenger improvement percent]`
- `[DATA: number of manual hypotheses tested]`
- `[DATA: number of AI hypotheses proposed, approved, rejected, executed]`
- `[DATA: where manual approach outperformed AI]`
- `[DATA: where AI found a useful direction faster]`
- `[DATA: anomaly benchmark precision, recall, F1, false-positive rate, review rate]`

## Narrative Spine

1. Retail inventory is a feedback loop, not a static count.
2. Forecasting alone does not solve inventory decisioning.
3. Enterprise retailers have closed-loop systems; SMB and mid-market retailers often do not.
4. ShelfOps packages that loop into a platform: data ingest, readiness, models, recommendations, human decisions, outcomes, and improvement.
5. I tested the DS side on real public retail benchmarks, not synthetic performance claims.
6. I ran manual hypotheses through the platform to try to improve the model.
7. I then let AI propose/run hypotheses through the same governed workflow.
8. The takeaway is that AI can compress DS iteration, but only if the workflow is reproducible, auditable, and human-gated.

## Manual DS Operating Plan

This is the path to run before the AI-assisted lane. The goal is to show real
data science judgment first: diagnose, form hypotheses, run controlled
experiments, interpret tradeoffs, and make promotion decisions.

### 0. Freeze The Experiment Charter

Before looking for improvements, write down the rules.

- Baseline model: `[DATA: champion version]`
- Dataset snapshot: `[DATA: M5 snapshot ID]`
- Forecast grain: `[DATA: store x product x day]`
- Holdout window: `[DATA]`
- Primary forecast metrics: WAPE, MASE, bias, interval coverage
- Decision metrics: simulated stockout exposure, simulated overstock exposure,
  order cost, holding cost, service level
- Claim boundary: M5 forecast evidence is `benchmark`; decision replay is
  `simulated`; no measured merchant ROI
- Promotion policy: challenger can move to shadow only if it passes model and
  decision gates

The point is to avoid moving the goalposts after a result appears.

### 1. Baseline EDA Outside The App

Do the first diagnostic work outside ShelfOps in a notebook or script. The app
should be the governed system of record, not a replacement for exploratory
analysis.

Questions to answer:

- What is the date range, SKU/store coverage, and category mix?
- Which categories and stores drive most volume?
- How much demand is intermittent or low velocity?
- Where does the champion overpredict or underpredict?
- Which segments have the worst WAPE, MASE, bias, or coverage?
- Are errors concentrated around price changes, events, weekends, holidays, or
  specific categories?
- Which forecast errors matter most for replenishment decisions?
- Does a metric improvement reduce simulated stockout or overstock exposure, or
  does it only improve global forecast error?

Artifacts to capture:

- `[CHART: category/store/velocity mix]`
- `[CHART: residuals by segment]`
- `[CHART: forecast bias by category and velocity band]`
- `[CHART: decision replay losses by segment]`
- `[TABLE: top failure modes ranked by business relevance]`

### 2. Convert Findings Into Hypotheses

Each hypothesis should have a retail reason. Avoid random parameter tuning as
the lead story.

Hypothesis template:

- Observation: `[what the EDA showed]`
- Retail rationale: `[why this should matter operationally]`
- Expected movement: `[which metric should move and in what direction]`
- Risk: `[what could get worse]`
- Spec change: `[which ShelfOps spec/template/override will test it]`
- Promotion gate: `[what must be true to keep it]`

Example:

Observation: slow movers are over-forecasted and create simulated overstock
exposure.

Retail rationale: intermittent items often need conservative calibration because
small absolute misses can produce unnecessary orders.

Expected movement: lower slow-mover bias and lower simulated overstock cost,
with no unacceptable service-level drop.

Spec change: conservative slow-mover challenger.

Promotion gate: keep only if overstock exposure improves and WAPE/MASE do not
regress beyond the allowed threshold.

### 3. Run The Governed Workflow In ShelfOps

After EDA and hypothesis design, use ShelfOps as the execution and audit layer.

Workflow:

1. Create or select a context package for the baseline model and dataset.
2. Create the manual hypothesis in Model Lab.
3. Materialize an executable experiment spec from an approved template.
4. Record the spec ID and spec hash.
5. Run the experiment through the app/API.
6. Review global metrics, segment metrics, uncertainty metrics, and decision
   replay metrics.
7. Record the decision: reject, keep for shadow, or promote as challenger.
8. Write the rationale in business language, not only model language.

For each run, capture:

- `[DATA: experiment ID]`
- `[DATA: hypothesis ID]`
- `[DATA: experiment spec ID]`
- `[DATA: spec hash]`
- `[DATA: baseline metrics]`
- `[DATA: challenger metrics]`
- `[DATA: segment deltas]`
- `[DATA: decision replay deltas]`
- `[DATA: promotion gate result]`
- `[SCREENSHOT: experiment run detail]`

### 4. Manual Hypothesis Queue

Start with 4-6 hypotheses. Enough to show rigor, not so many that the story
turns into a tuning dump.

Candidate queue:

1. Price/promo lag features
   - Retail reason: price changes and promotions should affect short-term demand.
   - Expected benefit: promoted/price-sensitive segments improve.

2. Velocity-segmented bias calibration
   - Retail reason: high-velocity and low-velocity SKUs have different error
     costs and bias patterns.
   - Expected benefit: segment bias improves without global degradation.

3. Conservative slow-mover tuning
   - Retail reason: intermittent demand can create costly over-ordering if the
     model chases noise.
   - Expected benefit: lower overstock exposure and better slow-mover bias.

4. Category-specific calibration
   - Retail reason: FOODS, HOBBIES, and HOUSEHOLD have different seasonality,
     substitutability, and demand frequency.
   - Expected benefit: category-level bias and coverage improve.

5. Calendar/event interaction
   - Retail reason: demand spikes can cluster around weekends, events, holidays,
     and known calendar effects.
   - Expected benefit: better peak-period behavior and lower under-forecasting.

6. Decision-cost-aware challenger
   - Retail reason: the best forecast metric may not be the best replenishment
     decision.
   - Expected benefit: improved simulated inventory tradeoffs even if WAPE only
     improves modestly.

### 5. Manual Interpretation

The strongest hiring-manager signal is not pretending every hypothesis worked.
The signal is showing disciplined interpretation.

For each run, answer:

- Did the metric move for the reason I expected?
- Did the improvement show up in the segment I targeted?
- Did the model improve business decision quality or only forecast error?
- Did any segment get worse enough to block promotion?
- What did this result teach me about the data or retail process?

End state:

- Best manual challenger: `[DATA]`
- Best manual challenger status: `[shadow / rejected / promoted candidate]`
- Main lesson: `[DATA]`
- Strongest failure: `[DATA]`
- Most useful domain insight: `[DATA]`

## AI-Assisted DS Operating Plan

Run this after the manual lane. The AI lane should be constrained to the same
evidence, templates, gates, and claim boundaries so the comparison is fair.

### 0. Give AI The Same Context

The AI should not get a vague prompt like "make the model better." It should get
the same context a data scientist would need:

- baseline metrics
- EDA summary
- segment failure table
- allowed datasets
- allowed experiment templates
- promotion gates
- claim boundaries
- previous manual run summaries, if the comparison is allowed to include them

Use two comparison modes if useful:

- blind mode: AI gets the baseline and EDA, but not manual results
- informed mode: AI gets manual results and is asked to find a different path

### 1. AI Proposes Hypotheses, Human Approves

The AI should propose hypotheses, not directly promote models.

For each AI proposal, log:

- prompt hash
- context package ID
- generated hypothesis
- retail rationale
- expected metric movement
- selected template/spec idea
- human decision: approved, rejected, edited
- human rationale

Reject proposals that:

- chase weak correlations without retail logic
- optimize only global WAPE while ignoring decision metrics
- require unavailable data
- imply measured ROI from benchmark data
- bypass promotion gates

### 2. Run Approved AI Hypotheses Through ShelfOps

Approved AI ideas should follow the same workflow as manual ideas:

1. Convert to a governed hypothesis.
2. Materialize an executable spec.
3. Run the experiment through ShelfOps.
4. Compare global, segment, uncertainty, and decision replay metrics.
5. Record promotion gate result.
6. Human reviews the final decision.

Capture:

- `[DATA: AI hypotheses proposed]`
- `[DATA: approved / rejected / edited]`
- `[DATA: AI spec hashes]`
- `[DATA: AI run metrics]`
- `[DATA: human review decisions]`
- `[SCREENSHOT: AI trace]`
- `[SCREENSHOT: AI lane in comparison report]`

### 3. Compare Manual vs AI

The comparison should not be framed only as "who got the best score." Compare
the process.

Comparison dimensions:

- Number of hypotheses proposed
- Number approved
- Number executed
- Number rejected for weak domain logic
- Best global metric improvement
- Best segment improvement
- Best decision replay improvement
- Number of iterations to reach a viable challenger
- Whether the idea was explainable to a retail operator
- Whether the run respected claim boundaries
- Whether the model improved the targeted failure mode

The strongest final takeaway is likely:

AI compressed hypothesis generation, but human DS judgment was still needed to
choose useful hypotheses, reject weak assumptions, interpret business tradeoffs,
and decide whether a challenger was safe to keep in shadow.

## Post Series

### Post 1: Retail Inventory Taught Me Feedback Loops

Goal: establish domain credibility and personal origin.

Rough draft:

I started working in retail inventory at Target while I was at UNC. At the time,
it was a practical job. I needed to pay for school, and inventory work was where
I spent a lot of my time.

The work was not glamorous, but it taught me how retail actually operates.
Shelf fills, inventory audits, backroom checks, suspect tasks, and item-level
corrections all pointed to the same underlying problem:

the system only works if the data keeps getting corrected by reality.

If the shelf was empty but the system said we had inventory, someone had to
investigate. If the backroom count was wrong, someone had to fix it. If a
product kept showing up in suspect tasks, the system was telling us there was a
gap between expected and observed behavior.

Years later, as I studied data science and machine learning, that loop started
to look very familiar. Forecasts, anomalies, replenishment decisions, feedback,
and governed model/policy improvement were all versions of the same idea.

Retail inventory is not just counting products. It is a decision loop.

That idea eventually became ShelfOps: an inventory decision platform that
connects forecasting, anomaly detection, replenishment recommendations, human
review, outcome tracking, and governed model/policy improvement in one workflow.

`[PHOTO: personal retail/inventory photo or neutral personal photo]`

`[SCREENSHOT: ShelfOps Replenishment Queue]`

### Post 2: Forecasting Is Not Inventory Decisioning

Goal: show domain maturity and explain why the platform exists.

Rough draft:

A better forecast is useful, but it is not the final retail decision.

Retail teams do not only need to know what demand might be. They need to answer:

- What should I order?
- Where should I place inventory?
- What service level should I target?
- What tradeoff am I making between stockouts, overstock, spoilage, order cost,
  holding cost, and working capital?

That is the gap I kept coming back to while building ShelfOps.

Forecasting is a model problem. Inventory decisioning is a system problem.

A forecast should flow into a recommendation. A recommendation should be
accepted, edited, or rejected by a human. The result should be measured later.
That outcome should feed back into future models and policies.

That is the loop ShelfOps is built around:

real data ingest -> data readiness -> forecast and uncertainty -> stockout /
overstock risk -> replenishment recommendation -> buyer decision -> outcome ->
model and policy improvement.

The important part is not just that a model exists. It is that every decision
has provenance, every metric has a label, and every recommendation can be traced
back to the data, model, and policy that produced it.

`[SCREENSHOT: recommendation drawer showing forecast interval, reorder point, order cost, holding cost, spoilage risk]`

`[DATA: example recommendation with provenance labels]`

### Post 3: Building ShelfOps For SMB Retailers

Goal: position product clearly without overclaiming.

Rough draft:

Large retailers have entire teams working on forecasting, replenishment,
inventory accuracy, anomaly detection, monitoring, and governance.

Smaller retailers usually do not.

That does not mean the problem is simpler. SMB and mid-market retailers still
deal with stockouts, stale inventory, missed demand, vendor constraints,
inventory inaccuracies, and buyer workload. They just have fewer people and less
infrastructure to solve it.

ShelfOps is my attempt to bring enterprise-style inventory intelligence into a
smaller-team workflow.

The product is not meant to be another dashboard that says forecast error went
down. It is meant to be an operating loop:

- ingest sales, inventory, product, supplier, and PO data
- validate whether the data is ready for modeling
- train auditable demand and anomaly models
- generate replenishment recommendations
- let buyers accept, edit, or reject decisions
- measure outcomes after reality arrives
- feed those outcomes back into future models and policies

The current build is pre-pilot. The model evidence uses public benchmarks:
M5/Walmart for demand forecasting and FreshRetailNet for stockout/anomaly
methodology. The measured merchant outcome path will come from CSV or Square
pilot data once a real pilot is running.

That distinction matters. Benchmark evidence is not merchant ROI, and ShelfOps
keeps those labels visible by design.

`[SCREENSHOT: Data Readiness page]`

`[SCREENSHOT: Model Lab showing demand forecast and anomaly model families]`

### Post 4: My First DS Pass On Retail Forecasting

Goal: show hands-on DS ability with real public retail data.

Rough draft:

After building the platform, I wanted to test the data science workflow itself.

Could I take real retail benchmark data, establish a baseline, identify where
the model struggled, form hypotheses, and run improvements through an auditable
workflow?

For the forecasting track, I used the M5/Walmart benchmark.

Baseline:

- Dataset: `[DATA: M5 subset/grain/date range]`
- Champion model: `[DATA: champion model/version]`
- Baseline WAPE: `[DATA]`
- Baseline MASE: `[DATA]`
- Bias: `[DATA]`
- Interval coverage: `[DATA]`
- Hard segments: `[DATA: slow movers, intermittent demand, promoted items, category/store segments]`

The first thing I wanted to understand was not just "is the model good?" It was:

where does it fail, and does that failure matter for inventory decisions?

A model can improve WAPE and still produce poor replenishment decisions if the
improvement is in the wrong segment. For inventory, a miss on a fast-moving
perishable item and a miss on a slow-moving household item do not have the same
business meaning.

So I treated the experiment as a model + decision problem:

- forecast quality
- segment behavior
- uncertainty quality
- simulated stockout exposure
- simulated overstock exposure
- order and holding cost tradeoffs

`[CHART: baseline forecast metrics]`

`[CHART: segment breakdown]`

`[SCREENSHOT: ShelfOps experiment run / spec hash]`

### Post 5: Six Hypotheses To Beat The Baseline

Goal: show rigorous hypothesis-driven DS iteration.

Rough draft:

I ran a small set of manual hypotheses through ShelfOps to try to beat the
baseline model.

The rule was simple: every experiment had to be reproducible. No notebook-only
runs. No unlabeled metrics. No silent feature changes. Each run needed a spec,
a hash, a result, and a promotion decision.

Hypotheses tested:

1. `[HYPOTHESIS 1: price/promo lag feature idea]`
   - Why: `[DOMAIN RATIONALE]`
   - Result: `[DATA]`
   - Decision: `[promote / reject / keep shadow]`

2. `[HYPOTHESIS 2: velocity-segmented calibration]`
   - Why: `[DOMAIN RATIONALE]`
   - Result: `[DATA]`
   - Decision: `[DATA]`

3. `[HYPOTHESIS 3: slow-mover conservative tuning]`
   - Why: `[DOMAIN RATIONALE]`
   - Result: `[DATA]`
   - Decision: `[DATA]`

4. `[HYPOTHESIS 4: calendar/holiday or promo interaction]`
   - Why: `[DOMAIN RATIONALE]`
   - Result: `[DATA]`
   - Decision: `[DATA]`

5. `[HYPOTHESIS 5: anomaly threshold or stockout detection profile]`
   - Why: `[DOMAIN RATIONALE]`
   - Result: `[DATA]`
   - Decision: `[DATA]`

6. `[HYPOTHESIS 6: final challenger attempt]`
   - Why: `[DOMAIN RATIONALE]`
   - Result: `[DATA]`
   - Decision: `[DATA]`

The best challenger was:

- Model/spec: `[DATA]`
- WAPE change: `[DATA]`
- MASE change: `[DATA]`
- Bias change: `[DATA]`
- Simulated stockout exposure change: `[DATA]`
- Simulated overstock/cost change: `[DATA]`
- Promotion gate result: `[DATA]`

The most useful lesson was `[FILL: what actually happened]`.

`[SCREENSHOT: experiment ledger with six runs]`

`[CHART: baseline vs challenger metrics]`

`[SCREENSHOT: promotion gate / shadow testing status]`

### Post 6: I Gave AI The Same DS Problem

Goal: connect the platform to AI-assisted DS workflows.

Rough draft:

After running my own hypotheses, I wanted to test a second question:

What happens if an AI system gets the same model context and is asked to improve
the same baseline?

I did not want this to be an unconstrained agent experiment. In real ML systems,
speed without governance is a problem.

So I gave the AI the same ShelfOps context package:

- baseline model evidence
- available datasets
- allowed experiment templates
- promotion gates
- claim boundaries
- previous run results

The AI could propose hypotheses, but the workflow still required:

- human review
- an executable experiment spec
- a reproducible spec hash
- benchmark/simulated provenance labels
- promotion gates
- audit logs

AI-assisted run summary:

- Hypotheses proposed: `[DATA]`
- Approved: `[DATA]`
- Rejected: `[DATA]`
- Executed: `[DATA]`
- Best AI challenger: `[DATA]`
- Best metric movement: `[DATA]`
- Where AI helped: `[DATA]`
- Where AI made weak assumptions: `[DATA]`

The interesting part was not simply whether AI beat my manual run. The
interesting part was how it searched.

Did it focus on features that actually had a plausible connection to demand?
Did it chase correlation without domain logic? Did it optimize model metrics
while ignoring decision costs? Did it find a hypothesis I missed?

That is where I think data science is moving.

AI can compress the iteration loop. But the data scientist's job becomes even
more important around problem framing, constraints, evidence quality, human
review, and business interpretation.

`[SCREENSHOT: AI hypothesis trace / prompt hash]`

`[SCREENSHOT: manual vs AI comparison report]`

`[CHART: manual best challenger vs AI best challenger]`

### Post 7: What This Taught Me About The Future Of DS

Goal: tie everything back to hiring signal and product thesis.

Rough draft:

This project changed how I think about data science work.

The traditional workflow is often framed as:

load data -> train model -> evaluate metrics -> deploy model.

Retail does not really work that way.

The useful workflow is closer to:

understand the operating decision -> define the metric tradeoff -> train the
model -> generate a recommendation -> let a human review it -> measure the
outcome -> update the next model or policy.

That is why I built ShelfOps as an MLOps platform, not just a model demo.

The manual DS work mattered because it forced me to reason through the domain:
promotions, seasonality, intermittent demand, inventory accuracy, stockouts,
overstock, spoilage, and cost tradeoffs.

The AI-assisted work mattered because it showed where the role might be going.
AI can help generate hypotheses and run iterations faster, but only if the
system around it creates reproducible runs, audit trails, clear promotion gates,
and human review.

My takeaway:

Data science is not disappearing. The role is shifting toward sharper problem
framing, better experiment systems, stronger governance, and more direct
connection to business decisions.

That is the space ShelfOps is built for.

`[SCREENSHOT: full ShelfOps loop or architecture diagram]`

`[DATA: final summary table of manual vs AI runs]`

## Final Portfolio Framing

Short version:

ShelfOps is an inventory decision and MLOps platform for SMB and mid-market
retailers. It connects retail operating data to demand forecasting, anomaly
detection, replenishment recommendations, human decision review, outcome
measurement, and governed model/policy improvement.

Long version:

ShelfOps came from seeing retail inventory as a closed-loop system. The product
uses real benchmark evidence to prove model and decision workflows, while
keeping business-impact claims separate until real merchant pilots produce
measured outcomes. The platform is also designed for where data science is
headed: AI-assisted hypothesis generation and faster iteration, constrained by
reproducible specs, audit logs, human approval, and promotion gates.

## Fill-In Checklist Before Publishing

- `[ ]` Capture screenshots from the current UI.
- `[ ]` Run the manual hypothesis sequence.
- `[ ]` Record each spec ID/hash and result.
- `[ ]` Run the AI-assisted hypothesis sequence.
- `[ ]` Record AI prompt hashes, approvals, rejections, and results.
- `[ ]` Produce manual-vs-AI comparison report.
- `[ ]` Update all metric placeholders.
- `[ ]` Re-check CLAIMS.md before posting.
- `[ ]` Make sure every business metric has provenance.
- `[ ]` Avoid measured ROI language until a real pilot exists.
