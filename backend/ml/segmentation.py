"""
Category segmentation helpers used by scheduled category-tier retraining.

This module remains intentionally small: the active runtime is global
LightGBM-first, but scheduled category-tier retrains still reference these
helpers. Removing the module breaks those scheduled jobs before training starts.
"""

from __future__ import annotations

from typing import Literal

CategoryTier = Literal["fresh", "general_merchandise", "hardware"]

TIER_TO_CATEGORIES: dict[CategoryTier, list[str]] = {
    "fresh": ["Produce", "Dairy", "Bakery", "Meat", "Meat & Seafood"],
    "general_merchandise": [
        "Grocery",
        "Frozen",
        "Beverages",
        "Household",
        "Health & Beauty",
        "Pet Supplies",
        "Baby",
        "Snacks",
    ],
    "hardware": ["Hardware"],
}

ALL_TIERS: tuple[CategoryTier, ...] = ("fresh", "general_merchandise", "hardware")


def get_tier_categories(tier: CategoryTier) -> list[str]:
    """Return the product categories belonging to a scheduled category tier."""
    categories = TIER_TO_CATEGORIES.get(tier)
    if categories is None:
        raise ValueError(f"Unknown tier '{tier}'. Known: {list(ALL_TIERS)}")
    return categories.copy()
