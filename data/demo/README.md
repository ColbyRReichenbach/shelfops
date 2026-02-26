# Summit Outdoor Supply — Demo Dataset

## Retailer Profile

**Summit Outdoor Supply** is a mid-size outdoor sporting goods retailer operating
a single store in the Mountain West region (Denver timezone). They sell gear
across categories including water sports, climbing, apparel, camping, and
footwear. Summit is a prototypical ShelfOps SMB customer: meaningful seasonal
swings, a handful of high-velocity SKUs, and a cluster of slow-moving specialty
items that are easy to over-buy.

- **Customer ID**: `00000000-0000-0000-0000-000000000099`
- **Store ID**: `00000000-0000-0000-0000-000000000099`
- **Timezone**: `America/Denver`
- **Tier**: `smb`
- **Data range**: Days 0–95 (cold-start + graduation + current)

---

## 10 Key SKUs

### Fast-Movers (5)

| Product ID | Name | Avg Daily Units | Category |
|------------|------|-----------------|----------|
| prod-001 | Trail Runner X3 Shoe | 22–35 | Footwear |
| prod-002 | Merino Base Layer Top | 18–28 | Apparel |
| prod-003 | Kayak Paddle Pro | 4–18 | Water Sports |
| prod-004 | Trek Lite Backpack 45L | 12–20 | Camping |
| prod-005 | Summit Fleece Jacket | 15–25 | Apparel |

### Slow-Movers (5)

| Product ID | Name | Avg Daily Units | Category |
|------------|------|-----------------|----------|
| prod-006 | Alpine Hardshell Jacket | 0–3 | Apparel |
| prod-007 | Climbing Harness Pro | 0–3 | Climbing |
| prod-008 | Splitboard Bindings | 0–2 | Winter Sports |
| prod-009 | Avalanche Safety Kit | 0–2 | Winter Sports |
| prod-010 | GPS Navigation Watch | 0–3 | Electronics |

---

## 3 Engineered Patterns

### 1. Summer Demand Spike — Kayak Paddle Pro (prod-003)

**Dataset window**: Days 52–58 (transactions_day031_090.csv)
**Pattern**: Demand jumps from ~5 units/day to ~18 units/day — a 3.6x spike
driven by Memorial Day weekend and the start of local rafting season.

**SHAP explanation produced**: `seasonal driver +38%`

This is the core stockout-prediction story for the demo. By day 91, prod-003
stock is getting critically low. ShelfOps detects the trend 2–3 days before
the shelf empties and fires an automated reorder.

---

### 2. Black Friday Lift — Apparel SKUs (prod-005, prod-006, prod-008)

**Dataset window**: Around day 82 (transactions_day031_090.csv)
**Pattern**: prod-005 (Fleece Jacket), prod-006 (Hardshell), and prod-008
(Splitboard Bindings) all see +30% volume lift on the Black Friday shopping
event window (days 82–84).

**SHAP explanation produced**: `promo event +29%`

Demonstrates that ShelfOps learns promotional calendars from POS history and
anticipates the inventory draw-down, preventing stock gaps on the highest-margin
items right before winter season.

---

### 3. Vendor X Delivery Failures — Climbing Harness (prod-007)

**Dataset window**: Days 32–34 (transactions_day031_090.csv)
**Pattern**: Sold-through units for prod-007 are halved during days 32–34
because Vendor X failed two consecutive deliveries. ShelfOps captures the
supply-side signal through inventory snapshot divergence.

**SHAP explanation produced**: `supplier variance +15%`

Illustrates the "safety stock buffer" recommendation workflow: when supplier
reliability drops, ShelfOps automatically increases the reorder point to absorb
the variance and avoid a stockout cascade.

---

## CSV File Layout

All three files share the same schema:

```
date,store_id,product_id,quantity,unit_price
```

| Column | Type | Description |
|--------|------|-------------|
| date | YYYY-MM-DD | Transaction date (Mountain time) |
| store_id | UUID | Store identifier |
| product_id | string | SKU identifier (prod-001 ... prod-010) |
| quantity | integer | Units sold that day (0 = no sales) |
| unit_price | float | Selling price per unit |

Files:
- `transactions_day000_030.csv` — 300 rows: 30 days x 10 SKUs (cold-start)
- `transactions_day031_090.csv` — 600 rows: 60 days x 10 SKUs (graduation)
- `transactions_day091_095.csv` — 50 rows: 5 days x 10 SKUs (current window)
