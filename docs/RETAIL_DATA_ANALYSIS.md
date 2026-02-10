# Retail Data Accuracy Analysis

> **Purpose**: Benchmark the ShelfOps synthetic data generator against real-world retail metrics to ensure accuracy.
>
> **Date**: 2026-02-09
>
> **Sources**: Target, Walmart, Lowe's annual filings (FY2024–25), NRF shrinkage reports, FMI grocery surveys, industry publications.

---

## 1. Store-Level Financial Metrics

| Metric | Target | Walmart | Lowe's | Grocery Avg |
|--------|--------|---------|--------|-------------|
| Daily transactions/store | ~2,745 | ~10,000 | ~800–1,200 | ~1,928 |
| Avg transaction value | $49–56 | $54 | $103 | $45.70 |
| Items per basket | 8–12 | 13 | 3–5 | 10–15 |
| Comp sales growth (FY24) | +0.1% | +4.8% | −2.7% | +1.8% |
| Inventory turnover | 6.2x | 9.07x | 3.2x | 14–18x (grocery) |

**Sources:**
- Target FY2024 10-K: comp sales +0.1%, traffic +1.4%, avg transaction −1.3% — [Target Q3 2025 Press Release](https://corporate.target.com/press-releases/2025/11/target-corporation-reports-third-quarter-fiscal-2025-earnings)
- Target inventory turnover 6.2x — [Finbox: Target Inventory Turnover](https://finbox.com/NYSE:TGT/explorer/inventory_turnover_ttm)
- Walmart FY2025 10-K: U.S. comp sales +4.8%, global e-commerce +20.8% — [Walmart Q4 FY25 Earnings](https://corporate.walmart.com/news/2025/02/20/walmart-releases-q4-and-fy25-earnings)
- Walmart avg $54/trip, 13 items, 10K customers/store/day — [Capital One Shopping: Walmart Statistics](https://capitaloneshopping.com/research/walmart-statistics/)
- Walmart inventory turnover 9.07x FY2025 — [Walmart 10-K SEC Filing](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000104169)
- Lowe's FY2024 10-K: comp sales −2.7%, avg ticket $103.37, turnover 3.2x — [Lowe's Annual Report 2024](https://www.lowes.com/l/about/annual-report)
- Grocery avg 13,500 transactions/week (~1,928/day) — [Capital One Shopping: Grocery Statistics](https://capitaloneshopping.com/research/grocery-store-statistics/)
- In-store supermarket avg $45.70/transaction — [FMI: The Power of Produce 2024](https://www.fmi.org/forms/store/ProductFormPublic/power-of-produce-2024)
- Target ~1B guest trips in H1 2024 / 1,989 stores — [Grocery Doppio / Target Investor Day](https://grocerydoppio.com/)

---

## 2. Gross Margins by Department

| Department | Gross Margin | Notes |
|------------|-------------|-------|
| Produce | 37–42% | Fresh dept, 2024 margin ~37%, down from 38% (2023) |
| Dairy | 40–50% | Grouped with fresh perishables |
| Meat & Seafood | 28–35% | Perimeter category; strongest fresh dept ($105B, +4.7% YoY) |
| Frozen | 35–50% | Buyers target 50%+; specialty retail 35%+ |
| Bakery | 48–55% | In-store production premium; highest shrink dept (8%) |
| Beverages | 35–45% | C-store: ~25% of gross margin from packaged beverages |
| Center Store (Grocery) | 25–30% | Kroger overall 22.3%; independents 27.4% |
| Household | 30–40% | Non-grocery general merchandise |
| Health & Beauty | 40–50% | High margin but ORC target |
| Hardware | 35–45% | Lowe's/HD composite avg |

**Sources:**
- Independent grocer margin 27.4%, Kroger 22.3%, Grocery Outlet 30.2% — [FMS Solutions: Grocery Margins 2024](https://www.fmssolutions.com/)
- Produce margin 37% (2024), down from 38% (2023) — [Gourmet Food Marketplace: Grocery Margins by Category](https://gourmetfoodmarketplace.com/)
- Dairy 40–50% grouped with fresh produce — [Gourmet Food Marketplace](https://gourmetfoodmarketplace.com/)
- Meat sales $105B (+4.7%), strongest fresh category — [Provisioner Online: Meat Department Performance 2024](https://www.provisioneronline.com/)
- Frozen buyers target 50%+ margin; specialty retail >35% — [AFFI: Frozen Food State of the Industry](https://affi.org/)
- Deli 20–40%, Floral 46% (highest), center store packaged goods 1–3% net — [FoodStorm: Grocery Margins by Department](https://www.foodstorm.com/)
- Kroger Q1 2025 gross margin 23.0% — [Kroger Investor Relations](https://ir.kroger.com/)

---

## 3. Shrinkage Rates (NRF + Industry Data)

| Category | Annual Shrink % | Primary Cause |
|----------|----------------|---------------|
| **Industry average** | **1.6%** of sales | 36% external theft, 29% employee theft, rest admin/spoilage |
| Produce | 4.8% | Spoilage; 37% of all unsold food; banana 4.1%, papaya 43% |
| Bakery | 8.0% | Shortest shelf life; 6% of total store shrink |
| Dairy | 1.5–4.0% | 59% approaching expiration; eggs major damage contributor |
| Meat & Seafood | 3.0–5.0% | Spoilage + markdown losses |
| Frozen | 1.0–1.5% | Low spoilage, some theft |
| Center Store | 0.8–1.2% | Primarily theft |
| Household | 2.0–3.0% | ORC target |
| Health & Beauty | 2.5–3.0% | ORC target (electronics, HBC most targeted) |

> Industry total: $112.1B in losses (2022). Projected $132B in 2024.

**Sources:**
- NRF: Average shrink 1.6% of sales (FY2022), up from 1.4% (2021) — [NRF: National Retail Security Survey 2023](https://nrf.com/research/national-retail-security-survey-2023)
- $112.1B total losses; 65% from theft (internal + external) — [NRF: Retail Shrink Report](https://nrf.com/topics/loss-prevention-and-cybersecurity)
- 93% increase in shoplifting incidents 2019→2023 — [NRF: Impact of Retail Theft & Violence 2024](https://nrf.com/research/impact-retail-theft-violence-2024)
- Produce shrink 4.8% of retail sales; 37% of all unsold food — [Where's My Shrink?](https://wheresmyshrink.com/)
- Bakery shrink 8.0% of sales, 6% of total store shrink — [Where's My Shrink?](https://wheresmyshrink.com/)
- Dairy shrink 1.5% of sales; 59% approaching expiration — [Pacific Coast Food Waste Collaborative](https://pacificcoastcollaborative.org/)
- Overall store shrink 3% in FY2023 — [The Shelby Report](https://www.theshelbyreport.com/)
- National avg grocery shrinkage 2–3% of total sales — [Dojo Business: Grocery Shrinkage Rates](https://dojobusiness.com/)
- Produce accounts for 43.7% of surplus food (2023) — [ReFED: Food Waste Data](https://refed.org/)
- ORC targets: electronics, clothing, HBC — [Appriss Retail: Organized Retail Crime](https://apprissretail.com/)
- Projected $132B global retail shrinkage (2024) — [InVue: Retail Shrinkage Trends](https://invue.com/)

---

## 4. Seasonal Sales Patterns

| Period | Dates | Sales Lift | Most Impacted Categories |
|--------|-------|-----------|------------------------|
| Holiday | Nov 15 – Dec 31 | **+25–40%** | All; furniture +5.6%, electronics +3.7% (2024) |
| Back-to-School | Jul – Aug | **+10–15%** | Apparel, office, snacks, beverages |
| Summer | Jun – Aug | **+20–30%** | Beverages, frozen (ice cream), produce |
| Spring | Mar – May | **+15–25%** | Hardware/garden, produce, cleaning |
| Super Bowl week | Late Jan/early Feb | **+30–50%** | Snacks, beverages, frozen appetizers |
| Grilling season | May – Sep | **+20%** | Meat, charcoal, condiments |

**Sources:**
- Holiday 2024: +3.8% total retail (Nov 1 – Dec 24); furniture +5.6%, electronics +3.7% — [Mastercard SpendingPulse via Marketing Charts](https://www.marketingcharts.com/)
- Holiday 2024: +4.2% YoY (Nov–Dec combined), exceeding forecasts — [Bain & Company: Holiday Retail 2024](https://www.bain.com/insights/holiday-retail-recap-2024/)
- Back-to-school: $586/child spending; $1T+ total market (2024) — [S&P Global: Back-to-School 2024](https://www.spglobal.com/marketintelligence/)
- Back-to-school: 66% of budget spent by end of July — [Deloitte: Back-to-School Survey 2024](https://www2.deloitte.com/us/en/insights/industry/retail-distribution/back-to-school-survey.html)
- NRF 2024 retail growth forecast: 2.5–3.5%, reaching $5.23–5.28T — [NRF: 2024 Retail Forecast](https://nrf.com/media-center/press-releases/nrf-forecasts-2024-retail-sales)
- Overall retail volume slight fall −0.2% in 2024 — [Retail Research: Global Retail Sales](https://www.retailresearch.org/)
- September 2024: grocery +1% MoM, apparel +1.5% (late BTS), furniture −1.4% — [PYMNTS: Retail Sales September 2024](https://www.pymnts.com/)
- Online grocery +27% YoY in May 2025, delivery-dominant — [The Shelby Report: Online Grocery Trends](https://www.theshelbyreport.com/)

---

## 5. Day-of-Week Sales Pattern

| Day | Sales Index | Notes |
|-----|-------------|-------|
| Monday | 0.82 | Lowest volume day |
| Tuesday | 0.85 | Slight uptick |
| Wednesday | 0.92 | Mid-week restocking |
| Thursday | 0.98 | Pre-weekend stocking begins |
| Friday | 1.12 | Payday shopping |
| **Saturday** | **1.35** | **Peak day** |
| Sunday | 1.05 | Post-church / meal prep |

**Sources:**
- Industry consensus from grocery POS data aggregates — [Enterprise Apps Today: Walmart Store Statistics](https://www.enterpriseappstoday.com/)
- Average grocery store ~13,500 weekly transactions; Saturday peak — [Capital One Shopping](https://capitaloneshopping.com/research/grocery-store-statistics/)

---

## 6. Year-over-Year Growth by Category (2024)

| Category | YoY Growth | Volume Trend | Source |
|----------|-----------|-------------|--------|
| Grocery (total) | +1.8% | Volume flat, price-driven | JLL / FMI |
| Meat & Seafood | **+4.7%** | $105B total; fastest fresh | Provisioner Online |
| Beverages (LRB) | +3.3% | 36.4B gallons; energy drinks +5.7% | Beverage Marketing Corp |
| Frozen | +2.9% (Q1) | Unit sales returned to positive | AFFI |
| Produce | +2.2% (dollars) | Volume by weight declined slightly | Supermarket News |
| Household | +2.0% CAGR | $314B global market | Research and Markets |
| Health & Beauty | +3.5% est. | Strong OTC + skincare growth | Industry aggregate |
| Pet Supplies | +4.0% est. | Premium segment growing fast | Industry aggregate |
| Baby | +1.0% est. | Stable, necessity-driven | Industry aggregate |
| Hardware | +1.5% | Post-pandemic normalization | Lowe's / HD filings |

**Sources:**
- Grocery +1.8% spending increase 2023→2024 — [JLL: Retail Spending Trends](https://www.jll.com/)
- Meat #1 fresh category at $105B (+4.7%); prices +7.1% Dec 2024 — [Provisioner Online](https://www.provisioneronline.com/)
- Beverages: LRB retail sales $255.3B (+3.3%); volume ~36.4B gallons — [Beverage Marketing Corporation](https://www.beveragemarketing.com/)
- Frozen: +2.9% dollars Q1 2024, units positive first time in 25 months — [AFFI: State of the Frozen Food Industry](https://affi.org/)
- Produce: +2.2% dollar sales; frozen produce share rising to 8.9% — [Supermarket News: State of Produce 2024](https://www.supermarketnews.com/)
- Household products $314B global (2.0% CAGR 2019–2024) — [Research and Markets](https://www.researchandmarkets.com/)
- Online grocery sales +11.5% (2024 forecast) — [Oberlo: Online Grocery Statistics](https://www.oberlo.com/)
- Carbonated soft drinks slight volume uptick to 11.9B gallons — [Beverage Industry Magazine](https://www.bevindustry.com/)

---

## 7. Perishable Spoilage / Food Waste

| Category | Waste / Unsold % | Detail |
|----------|-----------------|--------|
| Produce | 37–44% of all unsold food | Banana shrink 4.1%, papaya 43%, turnip greens 63% |
| Dairy | 12–13% of all unsold food | 5.6% of milk not sold; 59% from approaching expiration |
| Bakery | 3–12% of all unsold food | 0.4–9.6% of sales value lost |
| Fresh overall | 35–40% of delivered inventory | Retailer-level waste estimate |

**Sources:**
- Produce: 37.2% of unsold food (2022), 43.7% of surplus (2023) — [ReFED: Food Waste Monitor](https://refed.org/) / [AgFunder News](https://agfundernews.com/)
- Dairy: 12.4% of unsold food (2022); 5.6% of milk unsold — [Pacific Coast Collaborative: Grocery Food Waste Report](https://pacificcoastcollaborative.org/)
- Bakery: 12.2% of unsold food (2022), 0.4–9.6% sales value lost — [ReFED](https://refed.org/) / [ResearchGate: Bread and Bakery Loss](https://www.researchgate.net/)
- Fresh product waste 35–40% of delivered inventory at retail — [Upcycled Food Association](https://www.upcycledfood.org/)
- Spoilage accounts for 20–40% of total store shrinkage — [Dojo Business](https://dojobusiness.com/)
- Supermarkets throw away 2.5–4% of potential revenue from surplus food — [Food Logistics](https://www.foodlogistics.com/)
- Dairy accounts for ~5% of overall food loss — [McKinsey: Reducing Food Loss](https://www.mckinsey.com/)

---

## 8. Gap Analysis: ShelfOps Synthesizer vs Reality

| # | Parameter | Current Value | Real-World Value | Severity |
|---|-----------|--------------|-----------------|----------|
| 1 | Margin calculation | Flat 40% all depts | 25–55% varies by dept | ❌ High |
| 2 | Daily demand range | 5–80, same all depts | Dairy 30–200, hardware 2–20 | ❌ High |
| 3 | Perishable shrinkage | 0.5–2%/day | Annual: produce 4.8%, bakery 8% | ⚠️ Overstated 3x |
| 4 | Non-perishable shrinkage | Missing (0%) | 1.6% avg, 2–3% HBC | ❌ Missing |
| 5 | Holiday spike | +30% flat | +25–40%, category-specific | ⚠️ Close |
| 6 | Day-of-week pattern | Mon/Tue inverted | Real: Mon lowest, Sat peak | ⚠️ Close |
| 7 | Promo frequency | 5% | 15–25% (category-dependent) | ❌ Too low |
| 8 | Promo lift | 1.5–3.0x | 1.3–4.0x (avg 2.0x) | ⚠️ OK |
| 9 | YoY growth | Not modeled | 1.0–4.7% by category | ❌ Missing |
| 10 | Store volume variance | None | ±15–25% by location | ❌ Missing |
| 11 | Shelf life (perishables) | 3–14 flat | Bakery 2–5, dairy 14–21 | ⚠️ Mixed |
| 12 | Super Bowl / event spikes | Missing | +30–50% snacks/beverages | ❌ Missing |

---

*Last Updated: 2026-02-09*
