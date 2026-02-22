"""
Enterprise Data Seeder — Generate Synthetic Retail Datasets

Creates deterministic synthetic data for exercising ShelfOps ingestion
pipelines (EDI/SFTP/Kafka) and integration observability paths.

What this generates:
  - 500+ products with GTINs/UPCs across 12 departments
  - 15 stores across 3 distribution zones with volume variance
  - 365 days of transaction history (3M+ rows)
  - Daily inventory snapshots with category-specific shrinkage
  - Seasonal patterns, promotional spikes, event spikes, and YoY growth
  - Sample EDI 846/850/856/810 files for the EDI adapter
  - Sample SFTP CSV files for the SFTP adapter

Run:
  python scripts/seed_enterprise_data.py
  python scripts/seed_enterprise_data.py --stores 30 --products 1000 --days 730

Datasets generated:
  data/seed/products.csv           Product catalog with GTINs
  data/seed/stores.csv             Store master data
  data/seed/transactions/          Daily transaction files (SFTP format)
  data/seed/inventory/             Daily inventory snapshots (SFTP format)
  data/seed/edi/                   Sample EDI X12 documents
  data/seed/events/                Sample Kafka event JSON files
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ── Constants (Synthetic profile defaults) ──────────────────────────────────

DEPARTMENTS = {
    "Grocery": {
        "subcategories": ["Canned Goods", "Pasta & Rice", "Condiments", "Baking", "Cereal", "Snacks"],
        "price_range": (1.99, 12.99),
        "margin_range": (0.25, 0.30),  # Center store: Kroger 22.3%, independents 27.4%
        "demand_range": (10, 80),  # Mid-range, high variety
        "perishable": False,
        "seasonal_factor": 0.05,
        "shelf_life_range": (180, 730),
        "shrink_rate": 0.010,  # 1.0% — primarily theft/admin
        "promo_rate": 0.22,  # Highest promo-driven category
        "holiday_weight": 1.0,
    },
    "Dairy": {
        "subcategories": ["Milk", "Cheese", "Yogurt", "Butter", "Eggs"],
        "price_range": (2.49, 8.99),
        "margin_range": (0.40, 0.50),  # High margin perishable group
        "demand_range": (30, 200),  # High-frequency staple
        "perishable": True,
        "seasonal_factor": 0.10,
        "shelf_life_range": (14, 21),  # 2-3 weeks
        "shrink_rate": 0.025,  # 2.5% — 59% from approaching expiration
        "promo_rate": 0.15,
        "holiday_weight": 0.8,
    },
    "Produce": {
        "subcategories": ["Fruits", "Vegetables", "Herbs", "Salad Mixes"],
        "price_range": (0.99, 9.99),
        "margin_range": (0.37, 0.42),  # 37% (2024), down from 38% (2023)
        "demand_range": (20, 150),  # Seasonal variation
        "perishable": True,
        "seasonal_factor": 0.30,
        "shelf_life_range": (3, 10),  # Very short
        "shrink_rate": 0.048,  # 4.8% — 37% of all unsold food
        "promo_rate": 0.12,  # Lower promo, more seasonal
        "holiday_weight": 0.7,
    },
    "Meat & Seafood": {
        "subcategories": ["Beef", "Poultry", "Pork", "Seafood"],
        "price_range": (4.99, 24.99),
        "margin_range": (0.28, 0.35),  # Perimeter category avg
        "demand_range": (8, 60),  # Higher price, lower volume
        "perishable": True,
        "seasonal_factor": 0.15,
        "shelf_life_range": (3, 7),  # Very short
        "shrink_rate": 0.040,  # 4.0% — spoilage + markdowns
        "promo_rate": 0.14,
        "holiday_weight": 1.2,  # Thanksgiving/Christmas prime
    },
    "Frozen": {
        "subcategories": ["Meals", "Vegetables", "Ice Cream", "Pizza", "Breakfast"],
        "price_range": (2.99, 14.99),
        "margin_range": (0.35, 0.50),  # Buyers target 50%+
        "demand_range": (10, 70),  # Consistent mid-range
        "perishable": False,
        "seasonal_factor": 0.20,
        "shelf_life_range": (180, 545),
        "shrink_rate": 0.012,  # 1.2% — low spoilage
        "promo_rate": 0.18,
        "holiday_weight": 1.1,
    },
    "Beverages": {
        "subcategories": ["Water", "Soda", "Juice", "Coffee", "Tea", "Sports Drinks", "Energy Drinks"],
        "price_range": (0.99, 8.99),
        "margin_range": (0.35, 0.45),  # Strong category margin
        "demand_range": (25, 120),  # High summer demand
        "perishable": False,
        "seasonal_factor": 0.25,
        "shelf_life_range": (180, 365),
        "shrink_rate": 0.012,  # 1.2%
        "promo_rate": 0.20,
        "holiday_weight": 0.9,
    },
    "Bakery": {
        "subcategories": ["Bread", "Rolls", "Pastries", "Cakes"],
        "price_range": (2.49, 12.99),
        "margin_range": (0.48, 0.55),  # In-store production premium
        "demand_range": (15, 90),  # High spoilage offset
        "perishable": True,
        "seasonal_factor": 0.15,
        "shelf_life_range": (2, 5),  # Very short — highest shrink dept
        "shrink_rate": 0.080,  # 8.0% — shortest shelf life
        "promo_rate": 0.10,
        "holiday_weight": 1.5,  # Holiday baking spike
    },
    "Household": {
        "subcategories": ["Cleaning", "Paper Products", "Laundry", "Trash Bags"],
        "price_range": (3.99, 19.99),
        "margin_range": (0.30, 0.40),  # Non-grocery general merchandise
        "demand_range": (5, 40),  # Lower frequency purchases
        "perishable": False,
        "seasonal_factor": 0.05,
        "shelf_life_range": (365, 1095),
        "shrink_rate": 0.020,  # 2.0% — ORC target
        "promo_rate": 0.18,
        "holiday_weight": 0.6,
    },
    "Health & Beauty": {
        "subcategories": ["Oral Care", "Hair Care", "Skin Care", "Medicine"],
        "price_range": (2.99, 29.99),
        "margin_range": (0.40, 0.50),  # High margin category
        "demand_range": (3, 30),  # Low volume, high margin
        "perishable": False,
        "seasonal_factor": 0.08,
        "shelf_life_range": (365, 730),
        "shrink_rate": 0.025,  # 2.5% — ORC target (NRF)
        "promo_rate": 0.15,
        "holiday_weight": 1.3,  # Gift sets, stocking stuffers
    },
    "Pet Supplies": {
        "subcategories": ["Dog Food", "Cat Food", "Treats", "Accessories"],
        "price_range": (4.99, 39.99),
        "margin_range": (0.30, 0.40),  # Moderate margin
        "demand_range": (5, 35),  # Loyal repeat buyers
        "perishable": False,
        "seasonal_factor": 0.05,
        "shelf_life_range": (365, 730),
        "shrink_rate": 0.010,  # 1.0%
        "promo_rate": 0.12,
        "holiday_weight": 0.8,
    },
    "Baby": {
        "subcategories": ["Diapers", "Formula", "Baby Food", "Wipes"],
        "price_range": (5.99, 34.99),
        "margin_range": (0.30, 0.38),  # Necessity-driven
        "demand_range": (5, 40),  # Necessity-driven
        "perishable": False,
        "seasonal_factor": 0.03,
        "shelf_life_range": (365, 730),
        "shrink_rate": 0.008,  # 0.8% — low theft
        "promo_rate": 0.14,
        "holiday_weight": 0.5,
    },
    "Hardware": {
        "subcategories": ["Tools", "Fasteners", "Paint", "Electrical", "Plumbing"],
        "price_range": (2.99, 89.99),
        "margin_range": (0.35, 0.45),  # Lowe's/HD avg
        "demand_range": (2, 20),  # Low volume, high ticket
        "perishable": False,
        "seasonal_factor": 0.20,
        "shelf_life_range": (730, 1825),
        "shrink_rate": 0.015,  # 1.5%
        "promo_rate": 0.08,  # Low promo frequency
        "holiday_weight": 0.4,
    },
}

# Year-over-year growth rates by category (2024 actuals)
# Source: JLL, Provisioner Online, Beverage Marketing Corp, AFFI, etc.
YOY_GROWTH = {
    "Grocery": 0.018,  # +1.8%
    "Produce": 0.022,  # +2.2% dollar sales
    "Dairy": 0.015,  # +1.5%
    "Meat & Seafood": 0.047,  # +4.7% (strongest fresh — $105B total)
    "Frozen": 0.029,  # +2.9% Q1 2024
    "Beverages": 0.033,  # +3.3% ($255.3B retail)
    "Bakery": 0.020,  # +2.0%
    "Household": 0.020,  # +2.0% CAGR
    "Health & Beauty": 0.035,  # +3.5%
    "Pet Supplies": 0.040,  # +4.0% (premium segment growing fast)
    "Baby": 0.010,  # +1.0% stable
    "Hardware": 0.015,  # +1.5% post-pandemic normalization
}

BRANDS = [
    "NatureBest",
    "FreshFirst",
    "PureChoice",
    "ValuePack",
    "GreenHarvest",
    "HomeBasics",
    "FieldFresh",
    "PrimeSelect",
    "DailyEssentials",
    "TopShelf",
    "ClearSpring",
    "SunValley",
    "BlueRidge",
    "GoldenCrest",
    "PeakPerformance",
]

STORE_LOCATIONS = [
    # (name, city, state, zip, lat, lon, timezone, volume_multiplier)
    # Volume multipliers model real ±25% variance in traffic by location
    # Zone 1: Upper Midwest (Target country)
    ("Minneapolis-Main", "Minneapolis", "MN", "55401", 44.9778, -93.2650, "US/Central", 1.20),
    ("Minneapolis-South", "Bloomington", "MN", "55431", 44.8408, -93.2983, "US/Central", 1.00),
    ("St Paul", "St Paul", "MN", "55101", 44.9537, -93.0900, "US/Central", 0.85),
    ("Chicago-Loop", "Chicago", "IL", "60601", 41.8781, -87.6298, "US/Central", 1.25),
    ("Chicago-North", "Evanston", "IL", "60201", 42.0451, -87.6877, "US/Central", 0.95),
    # Zone 2: Southeast
    ("Charlotte", "Charlotte", "NC", "28202", 35.2271, -80.8431, "US/Eastern", 1.05),
    ("Atlanta-Midtown", "Atlanta", "GA", "30309", 33.7812, -84.3865, "US/Eastern", 1.15),
    ("Atlanta-Buckhead", "Atlanta", "GA", "30326", 33.8413, -84.3798, "US/Eastern", 1.10),
    ("Nashville", "Nashville", "TN", "37201", 36.1627, -86.7816, "US/Central", 1.00),
    ("Raleigh", "Raleigh", "NC", "27601", 35.7796, -78.6382, "US/Eastern", 0.90),
    # Zone 3: West
    ("Denver", "Denver", "CO", "80202", 39.7392, -104.9903, "US/Mountain", 1.05),
    ("Phoenix", "Phoenix", "AZ", "85004", 33.4484, -112.0740, "US/Mountain", 0.95),
    ("Portland", "Portland", "OR", "97201", 45.5152, -122.6784, "US/Pacific", 0.90),
    ("Seattle", "Seattle", "WA", "98101", 47.6062, -122.3321, "US/Pacific", 1.10),
    ("LA-Downtown", "Los Angeles", "CA", "90012", 34.0522, -118.2437, "US/Pacific", 1.15),
]

SUPPLIERS = [
    ("Heartland Distributors", "orders@heartland-dist.com", 5, 0.94),
    ("Pacific Coast Foods", "purchasing@pacificcoast.com", 7, 0.91),
    ("National Grocery Supply", "supply@ngs.com", 3, 0.97),
    ("Fresh Direct Wholesale", "orders@freshdirectws.com", 4, 0.93),
    ("Metro Distribution Co", "logistics@metrodist.com", 6, 0.89),
]


# ── Generators ─────────────────────────────────────────────────────────────


def generate_gtin() -> str:
    """Generate a realistic 14-digit GTIN (GS1 standard)."""
    prefix = "00"  # Indicator digit + GS1 company prefix
    company = f"{random.randint(10000, 99999):05d}"
    item = f"{random.randint(10000, 99999):05d}"
    base = prefix + company + item
    # Calculate check digit (mod 10)
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base))
    check = (10 - (total % 10)) % 10
    return base + str(check)


def generate_upc_from_gtin(gtin: str) -> str:
    """Extract 12-digit UPC from 14-digit GTIN."""
    return gtin[2:]


def generate_products(n: int) -> list[dict[str, Any]]:
    """Generate n products with realistic, category-specific attributes."""
    products = []
    dept_list = list(DEPARTMENTS.keys())

    for i in range(n):
        dept = dept_list[i % len(dept_list)]
        info = DEPARTMENTS[dept]
        subcat = random.choice(info["subcategories"])
        brand = random.choice(BRANDS)
        gtin = generate_gtin()

        # Per-department margin calculation (replaces flat 40%)
        margin = random.uniform(*info["margin_range"])
        price = round(random.uniform(*info["price_range"]), 2)
        cost = round(price * (1 - margin), 2)

        # Per-department demand range (replaces flat 5-80)
        demand_lo, demand_hi = info["demand_range"]
        avg_demand = round(random.uniform(demand_lo, demand_hi), 1)

        # Per-department shelf life (replaces flat 3-14 / 180-730)
        shelf_lo, shelf_hi = info["shelf_life_range"]
        shelf_life = random.randint(shelf_lo, shelf_hi)

        products.append(
            {
                "product_id": str(uuid.uuid4()),
                "sku": f"SKU-{i + 1:05d}",
                "gtin": gtin,
                "upc": generate_upc_from_gtin(gtin),
                "name": f"{brand} {subcat} #{i + 1}",
                "category": dept,
                "subcategory": subcat,
                "brand": brand,
                "unit_cost": cost,
                "unit_price": price,
                "margin_pct": round(margin * 100, 1),
                "weight": round(random.uniform(0.1, 25.0), 2),
                "shelf_life_days": shelf_life,
                "is_perishable": info["perishable"],
                "is_seasonal": random.random() < info["seasonal_factor"],
                "supplier_idx": random.randint(0, len(SUPPLIERS) - 1),
                "avg_daily_demand": avg_demand,
            }
        )

    return products


def seasonal_multiplier(day_of_year: int, category: str) -> float:
    """
    Calculate seasonal demand multiplier.
    Models real retail patterns validated against industry data:
      - Beverages peak in summer (+20-30%)
      - Frozen peaks in summer (ice cream)
      - Produce peaks spring-summer
      - Hardware peaks spring (garden/renovation)
      - Holiday spike in Nov-Dec (+25-40%, category-weighted)
      - Super Bowl spike late Jan (+30-50% snacks/beverages)
      - Back-to-school Jul-Aug (+10-15%)
      - Grilling season May-Sep (+20% meat/condiments)
    """
    base = 1.0
    info = DEPARTMENTS.get(category, {})
    amplitude = info.get("seasonal_factor", 0.1)
    holiday_weight = info.get("holiday_weight", 1.0)

    # Category-specific seasonal peak day (0-365)
    peaks = {
        "Beverages": 180,  # July
        "Frozen": 195,  # Mid-July
        "Produce": 150,  # June
        "Hardware": 120,  # May
        "Bakery": 340,  # Early Dec (holiday baking)
        "Meat & Seafood": 185,  # Summer grilling
        "Household": 90,  # Spring cleaning
    }

    peak_day = peaks.get(category, 180)
    seasonal = amplitude * math.cos(2 * math.pi * (day_of_year - peak_day) / 365)

    # Holiday spike (Nov 15 – Dec 31) — per-category weighting
    # Real data: +25-40% overall; bakery 1.5x, HBC 1.3x, hardware 0.4x
    if 319 <= day_of_year <= 365:
        holiday_intensity = 0.35 * holiday_weight  # Base 35%, scaled by category
        holiday_curve = 1 - abs(day_of_year - 350) / 31
        base += holiday_intensity * holiday_curve

    # Super Bowl week (late Jan, day ~28-35) — snacks, beverages, frozen appetizers
    if 28 <= day_of_year <= 35:
        superbowl_categories = {
            "Grocery": 0.30,
            "Beverages": 0.45,
            "Frozen": 0.35,
            "Meat & Seafood": 0.20,
            "Dairy": 0.15,
        }
        if category in superbowl_categories:
            proximity = 1 - abs(day_of_year - 32) / 4
            base += superbowl_categories[category] * max(0, proximity)

    # Back-to-school (Jul – Aug, days ~182-244)
    if 182 <= day_of_year <= 244:
        bts_categories = {"Grocery": 0.10, "Beverages": 0.12, "Household": 0.08}
        base += bts_categories.get(category, 0.05)

    # Grilling season (May – Sep, days ~121-273)
    if 121 <= day_of_year <= 273:
        grill_categories = {"Meat & Seafood": 0.20, "Grocery": 0.08, "Beverages": 0.10}
        if category in grill_categories:
            # Peak in July, taper at edges
            grill_peak = 197  # Mid-July
            grill_intensity = max(0, 1 - abs(day_of_year - grill_peak) / 76)
            base += grill_categories[category] * grill_intensity

    return max(0.5, base + seasonal)


def day_of_week_factor(weekday: int) -> float:
    """
    Real grocery day-of-week sales index.
    Source: Industry POS data aggregates.
    Saturday is peak (+35% vs baseline), Monday is lowest.
    """
    # 0=Monday ... 6=Sunday
    factors = [0.82, 0.85, 0.92, 0.98, 1.12, 1.35, 1.05]
    return factors[weekday]


def yoy_growth_factor(days_from_oldest: int, total_days: int, category: str) -> float:
    """
    Apply year-over-year growth trend so recent data is higher than old data.
    This makes multi-year datasets realistic — meat growing 4.7%, beverages 3.3%, etc.
    """
    yoy_rate = YOY_GROWTH.get(category, 0.018)  # Default to grocery avg
    years_elapsed = days_from_oldest / 365.0
    return 1.0 + (yoy_rate * years_elapsed)


def generate_transactions(
    products: list[dict],
    stores: list[dict],
    days: int,
    output_dir: Path,
) -> int:
    """
    Generate daily transaction files (SFTP-style CSV).
    Returns total transaction count.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    now = datetime.utcnow()

    for day_offset in range(days):
        date = now - timedelta(days=day_offset)
        day_of_year = date.timetuple().tm_yday
        weekday = date.weekday()
        date_str = date.strftime("%Y%m%d")

        # day_offset=0 is today (most recent), day_offset=days-1 is oldest
        days_from_oldest = days - 1 - day_offset

        filepath = output_dir / f"DAILY_SALES_{date_str}.csv"
        rows = []

        for store in stores:
            store_volume = store.get("volume_multiplier", 1.0)

            # Each store sells a subset of products each day
            active_products = random.sample(
                products,
                k=min(
                    len(products),
                    random.randint(
                        int(len(products) * 0.5),
                        int(len(products) * 0.85),
                    ),
                ),
            )

            for product in active_products:
                base_demand = product["avg_daily_demand"]
                seasonal = seasonal_multiplier(day_of_year, product["category"])
                dow = day_of_week_factor(weekday)
                yoy = yoy_growth_factor(days_from_oldest, days, product["category"])

                # Add noise
                noise = random.gauss(1.0, 0.15)

                qty = max(1, int(base_demand * seasonal * dow * yoy * store_volume * noise))

                # Promotional spikes — category-specific frequency
                dept_info = DEPARTMENTS.get(product["category"], {})
                promo_rate = dept_info.get("promo_rate", 0.15)
                if random.random() < promo_rate:
                    qty = int(qty * random.uniform(1.3, 4.0))

                rows.append(
                    {
                        "TRANS_ID": str(uuid.uuid4())[:8],
                        "STORE_NBR": store["external_code"],
                        "ITEM_NBR": product["sku"],
                        "UPC": product["upc"],
                        "QTY_SOLD": qty,
                        "UNIT_PRICE": product["unit_price"],
                        "SALE_AMT": round(qty * product["unit_price"], 2),
                        "TRANS_DATE": date.strftime("%Y-%m-%d"),
                        "TRANS_TIME": f"{random.randint(6, 22):02d}:{random.randint(0, 59):02d}:00",
                        "TRANS_TYPE": "SALE",
                    }
                )

        # Write daily file
        if rows:
            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

            total += len(rows)
        if day_offset % 30 == 0:
            print(f"  📊 Generated {date_str}: {len(rows)} transactions ({total:,} total)")

    return total


def generate_inventory_snapshots(
    products: list[dict],
    stores: list[dict],
    days: int,
    output_dir: Path,
) -> None:
    """Generate daily inventory snapshot files (SFTP-style CSV)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow()

    # Initialize inventory levels
    inventory: dict[tuple[str, str], int] = {}
    for store in stores:
        for product in products:
            key = (store["external_code"], product["sku"])
            inventory[key] = random.randint(50, 500)

    for day_offset in range(days, -1, -1):  # Oldest first
        date = now - timedelta(days=day_offset)
        date_str = date.strftime("%Y%m%d")
        filepath = output_dir / f"INV_SNAPSHOT_{date_str}.csv"
        rows = []

        for store in stores:
            for product in products:
                key = (store["external_code"], product["sku"])
                qty = inventory[key]

                # Simulate daily consumption + replenishment
                daily_demand = int(product["avg_daily_demand"] * random.uniform(0.7, 1.3))
                qty -= daily_demand

                # Shrinkage — NRF/industry annual rates, converted to daily
                # Applied to ALL categories (not just perishables)
                dept_info = DEPARTMENTS.get(product["category"], {})
                annual_shrink = dept_info.get("shrink_rate", 0.016)
                daily_shrink_rate = annual_shrink / 365
                shrinkage = max(0, int(qty * daily_shrink_rate * random.uniform(0.5, 2.0)))
                qty -= shrinkage

                # Replenishment (when below 30% of max)
                max_stock = int(product["avg_daily_demand"] * 14)  # 2 weeks supply
                if qty < max_stock * 0.3:
                    reorder = random.randint(max_stock, max_stock * 2)
                    qty += reorder

                qty = max(0, qty)
                inventory[key] = qty

                rows.append(
                    {
                        "STORE_NBR": store["external_code"],
                        "ITEM_NBR": product["sku"],
                        "UPC": product["upc"],
                        "GTIN": product["gtin"],
                        "ON_HAND_QTY": qty,
                        "ON_ORDER_QTY": random.randint(0, max_stock) if qty < max_stock * 0.5 else 0,
                        "SNAPSHOT_DATE": date.strftime("%Y-%m-%d"),
                    }
                )

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        if day_offset % 30 == 0:
            print(f"  📦 Generated inventory snapshot: {date_str}")


def generate_edi_846_files(
    products: list[dict],
    stores: list[dict],
    output_dir: Path,
    count: int = 5,
) -> None:
    """Generate sample EDI 846 (Inventory Inquiry) documents."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for i in range(count):
        date = datetime.utcnow() - timedelta(days=i)
        date_str = date.strftime("%y%m%d")
        date_long = date.strftime("%Y%m%d")
        time_str = date.strftime("%H%M")
        store = random.choice(stores)
        subset = random.sample(products, k=min(50, len(products)))

        segments = [
            f"ISA*00*          *00*          *ZZ*RETAILER       *ZZ*SHELFOPS       *{date_str}*{time_str}*U*00401*{i + 1:09d}*0*P*>",
            f"GS*IB*RETAILER*SHELFOPS*{date_long}*{time_str}*{i + 1}*X*004010",
            f"ST*846*{i + 1:04d}",
        ]

        for j, product in enumerate(subset, 1):
            segments.extend(
                [
                    f"LIN*{j}*UP*{product['upc']}*IN*{product['gtin']}",
                    f"QTY*33*{random.randint(10, 500)}*EA",
                    f"QTY*02*{random.randint(0, 200)}*EA",
                    f"DTM*405*{date_long}",
                    f"N1*WH*{store['name']}*92*{store['external_code']}",
                ]
            )

        seg_count = len(segments) + 1  # +1 for SE
        segments.append(f"SE*{seg_count}*{i + 1:04d}")
        segments.append(f"GE*1*{i + 1}")
        segments.append(f"IEA*1*{i + 1:09d}")

        filepath = output_dir / f"EDI846_{date_long}_{i + 1:03d}.edi"
        with open(filepath, "w") as f:
            f.write("~\n".join(segments) + "~")

    print(f"  📄 Generated {count} EDI 846 files")


def generate_edi_850_files(
    products: list[dict],
    stores: list[dict],
    output_dir: Path,
    count: int = 5,
) -> None:
    """Generate sample EDI 850 (Purchase Order) documents."""
    output_dir.mkdir(parents=True, exist_ok=True)
    supplier_ids = [f"SUPPLIER_{i + 1:03d}" for i in range(len(SUPPLIERS))]

    for i in range(count):
        date = datetime.utcnow() - timedelta(days=i)
        date_str = date.strftime("%y%m%d")
        date_long = date.strftime("%Y%m%d")
        time_str = date.strftime("%H%M")
        po_number = f"PO-{random.randint(10000, 99999)}"
        vendor_id = random.choice(supplier_ids)
        store = random.choice(stores)
        subset = random.sample(products, k=min(10, len(products)))

        segments = [
            f"ISA*00*          *00*          *ZZ*SHELFOPS       *ZZ*{vendor_id:<15}*{date_str}*{time_str}*U*00401*{i + 1:09d}*0*P*>",
            f"GS*PO*SHELFOPS*{vendor_id}*{date_long}*{time_str}*{i + 1}*X*004010",
            f"ST*850*{i + 1:04d}",
            f"BEG*00*NE*{po_number}**{date_long}",
            f"N1*ST*{store['name']}*92*{store['external_code']}",
            "N3*123 Retail Ave",
            f"N4*{store['city']}*{store['state']}*{store['zip_code']}",
        ]

        for j, product in enumerate(subset, start=1):
            qty = random.randint(10, 100)
            segments.append(f"PO1*{j}*{qty}*EA*{product['unit_cost']:.2f}*PE*IN*{product['gtin']}")

        seg_count = len(segments) + 1  # +1 for SE
        segments.append(f"SE*{seg_count}*{i + 1:04d}")
        segments.append(f"GE*1*{i + 1}")
        segments.append(f"IEA*1*{i + 1:09d}")

        filepath = output_dir / f"EDI850_{date_long}_{i + 1:03d}.edi"
        with open(filepath, "w") as f:
            f.write("~\n".join(segments) + "~")

    print(f"  📄 Generated {count} EDI 850 files")


def generate_edi_856_files(
    products: list[dict],
    stores: list[dict],
    output_dir: Path,
    count: int = 5,
) -> None:
    """Generate sample EDI 856 (Advance Ship Notice) documents."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for i in range(count):
        date = datetime.utcnow() - timedelta(days=i)
        date_str = date.strftime("%y%m%d")
        date_long = date.strftime("%Y%m%d")
        time_str = date.strftime("%H%M")
        shipment_id = f"SHIP-{random.randint(100000, 999999)}"
        subset = random.sample(products, k=min(15, len(products)))

        segments = [
            f"ISA*00*          *00*          *ZZ*SUPPLIER       *ZZ*SHELFOPS       *{date_str}*{time_str}*U*00401*{i + 1:09d}*0*P*>",
            f"GS*SH*SUPPLIER*SHELFOPS*{date_long}*{time_str}*{i + 1}*X*004010",
            f"ST*856*{i + 1:04d}",
            f"BSN*00*{shipment_id}*{date_long}*{time_str}",
            "HL*1**S",
            "TD5*B*2*UPS*Ground",
            f"REF*CN*1Z{random.randint(100000000, 999999999)}",
            f"DTM*017*{(date + timedelta(days=3)).strftime('%Y%m%d')}",
        ]

        for j, product in enumerate(subset, start=1):
            po_number = f"PO-{random.randint(10000, 99999)}"
            qty = random.randint(5, 50)
            segments.extend(
                [
                    f"HL*{j + 1}*1*I",
                    f"LIN*{j}*IN*{product['gtin']}*UP*{product['upc']}",
                    f"SN1**{qty}*EA",
                    f"REF*PO*{po_number}",
                ]
            )

        seg_count = len(segments) + 1  # +1 for SE
        segments.append(f"SE*{seg_count}*{i + 1:04d}")
        segments.append(f"GE*1*{i + 1}")
        segments.append(f"IEA*1*{i + 1:09d}")

        filepath = output_dir / f"EDI856_{date_long}_{i + 1:03d}.edi"
        with open(filepath, "w") as f:
            f.write("~\n".join(segments) + "~")

    print(f"  📄 Generated {count} EDI 856 files")


def generate_edi_810_files(
    products: list[dict],
    stores: list[dict],
    output_dir: Path,
    count: int = 5,
) -> None:
    """Generate sample EDI 810 (Invoice) documents."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for i in range(count):
        date = datetime.utcnow() - timedelta(days=i)
        date_str = date.strftime("%y%m%d")
        date_long = date.strftime("%Y%m%d")
        time_str = date.strftime("%H%M")
        invoice_number = f"INV-{random.randint(100000, 999999)}"
        po_number = f"PO-{random.randint(10000, 99999)}"
        subset = random.sample(products, k=min(10, len(products)))

        segments = [
            f"ISA*00*          *00*          *ZZ*SUPPLIER       *ZZ*SHELFOPS       *{date_str}*{time_str}*U*00401*{i + 1:09d}*0*P*>",
            f"GS*IN*SUPPLIER*SHELFOPS*{date_long}*{time_str}*{i + 1}*X*004010",
            f"ST*810*{i + 1:04d}",
            f"BIG*{date_long}*{invoice_number}**{po_number}",
        ]

        total_cents = 0
        for j, product in enumerate(subset, start=1):
            qty = random.randint(5, 50)
            unit_price = product["unit_cost"]
            line_total = qty * unit_price
            total_cents += int(line_total * 100)
            segments.append(f"IT1*{j}*{qty}*EA*{unit_price:.2f}*PE*IN*{product['gtin']}")

        segments.append(f"TDS*{total_cents}")

        seg_count = len(segments) + 1  # +1 for SE
        segments.append(f"SE*{seg_count}*{i + 1:04d}")
        segments.append(f"GE*1*{i + 1}")
        segments.append(f"IEA*1*{i + 1:09d}")

        filepath = output_dir / f"EDI810_{date_long}_{i + 1:03d}.edi"
        with open(filepath, "w") as f:
            f.write("~\n".join(segments) + "~")

    print(f"  📄 Generated {count} EDI 810 files")


def generate_kafka_events(
    products: list[dict],
    stores: list[dict],
    output_dir: Path,
    count: int = 100,
) -> None:
    """Generate sample Kafka JSON event files for testing."""
    output_dir.mkdir(parents=True, exist_ok=True)

    events = []
    for i in range(count):
        store = random.choice(stores)
        items_count = random.randint(1, 8)
        items = []
        for _ in range(items_count):
            product = random.choice(products)
            qty = random.randint(1, 10)
            items.append(
                {
                    "sku": product["upc"],
                    "gtin": product["gtin"],
                    "quantity": qty,
                    "unit_price": product["unit_price"],
                    "total": round(qty * product["unit_price"], 2),
                }
            )

        event = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "event_type": "transaction.completed",
            "store_id": store["external_code"],
            "timestamp": (datetime.utcnow() - timedelta(minutes=random.randint(0, 1440))).isoformat() + "Z",
            "register_id": f"POS_{random.randint(1, 12):02d}",
            "items": items,
            "payment_method": random.choice(["credit_card", "debit_card", "cash", "mobile_pay"]),
            "total_amount": round(sum(it["total"] for it in items), 2),
        }
        events.append(event)

    filepath = output_dir / "sample_transactions.jsonl"
    with open(filepath, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    print(f"  ⚡ Generated {count} Kafka event samples")


# ── Main ───────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Generate enterprise-scale retail seed data")
    parser.add_argument("--products", type=int, default=500, help="Number of products (default: 500)")
    parser.add_argument("--stores", type=int, default=15, help="Number of stores (default: 15)")
    parser.add_argument("--days", type=int, default=365, help="Days of transaction history (default: 365)")
    parser.add_argument("--output", type=str, default="data/seed", help="Output directory")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("🏪 ShelfOps Enterprise Data Generator (v2)")
    print("=" * 60)
    print(f"  Products:     {args.products}")
    print(f"  Stores:       {args.stores}")
    print(f"  Days:         {args.days}")
    print(f"  Output:       {output}")
    print("  Profile:      synthetic enterprise integration test data")
    print()

    # ── Products ──────────────────────────────────────────────
    print("📦 Generating product catalog...")
    products = generate_products(args.products)
    products_file = output / "products.csv"
    with open(products_file, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "product_id",
                "sku",
                "gtin",
                "upc",
                "name",
                "category",
                "subcategory",
                "brand",
                "unit_cost",
                "unit_price",
                "margin_pct",
                "weight",
                "shelf_life_days",
                "is_perishable",
                "is_seasonal",
            ],
        )
        writer.writeheader()
        for p in products:
            row = {k: v for k, v in p.items() if k in writer.fieldnames}
            writer.writerow(row)
    print(f"  ✅ {len(products)} products → {products_file}")

    # Print margin stats for verification
    by_dept: dict[str, list[float]] = {}
    for p in products:
        by_dept.setdefault(p["category"], []).append(p["margin_pct"])
    print("\n  📊 Margin verification (avg by dept):")
    for dept, margins in sorted(by_dept.items()):
        avg_m = sum(margins) / len(margins)
        target = DEPARTMENTS[dept]["margin_range"]
        status = "✅" if target[0] * 100 <= avg_m <= target[1] * 100 else "⚠️"
        print(f"     {status} {dept:20s}: {avg_m:5.1f}% (target: {target[0] * 100:.0f}–{target[1] * 100:.0f}%)")

    # ── Stores ────────────────────────────────────────────────
    print("\n🏬 Generating store master data...")
    stores_data = STORE_LOCATIONS[: args.stores]
    stores = []
    for i, (name, city, state, zip_code, lat, lon, tz, vol_mult) in enumerate(stores_data):
        stores.append(
            {
                "store_id": str(uuid.uuid4()),
                "external_code": f"STR-{i + 1:03d}",
                "name": name,
                "city": city,
                "state": state,
                "zip_code": zip_code,
                "lat": lat,
                "lon": lon,
                "timezone": tz,
                "volume_multiplier": vol_mult,
            }
        )
    stores_file = output / "stores.csv"
    with open(stores_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(stores[0].keys()))
        writer.writeheader()
        writer.writerows(stores)
    print(f"  ✅ {len(stores)} stores → {stores_file}")

    # ── Transactions ──────────────────────────────────────────
    print(f"\n💳 Generating {args.days} days of transactions...")
    tx_count = generate_transactions(
        products,
        stores,
        args.days,
        output / "transactions",
    )
    print(f"  ✅ {tx_count:,} total transactions")

    # ── Inventory Snapshots ───────────────────────────────────
    print(f"\n📦 Generating {args.days} days of inventory snapshots...")
    generate_inventory_snapshots(
        products,
        stores,
        args.days,
        output / "inventory",
    )
    print("  ✅ Inventory snapshots generated")

    # ── EDI Files ─────────────────────────────────────────────
    print("\n📄 Generating EDI X12 sample files...")
    generate_edi_846_files(products, stores, output / "edi", count=10)
    generate_edi_850_files(products, stores, output / "edi", count=5)
    generate_edi_856_files(products, stores, output / "edi", count=5)
    generate_edi_810_files(products, stores, output / "edi", count=5)

    # ── Kafka Events ──────────────────────────────────────────
    print("\n⚡ Generating Kafka event samples...")
    generate_kafka_events(products, stores, output / "events", count=200)

    # ── Summary ───────────────────────────────────────────────
    print()
    print("=" * 60)
    print("✅ Enterprise data generation complete! (v2)")
    print("=" * 60)
    print(f"\n  📁 Output directory: {output}/")
    print(f"  📊 Products:          {len(products)} with GTINs + per-dept margins")
    print(f"  🏬 Stores:            {len(stores)} across 3 zones (volume-weighted)")
    print(f"  💳 Transactions:      {tx_count:,} rows (with YoY growth + event spikes)")
    print("  📄 EDI files:         25 sample documents (846/850/856/810)")
    print("  ⚡ Kafka events:      200 sample events")
    print("\n  Copy transactions/ and inventory/ to SFTP staging dir")
    print("  Copy edi/ to /data/edi/inbound for EDI adapter testing")
    print()


if __name__ == "__main__":
    main()
