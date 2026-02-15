"""
Category Model Segmentation — Route products to category-specific models.

ShelfOps trains separate demand forecast models for different product categories
because demand patterns differ fundamentally:
  - Fresh (Produce, Dairy, Bakery, Meat): Short shelf life, high spoilage,
    weather-sensitive, different seasonality peaks
  - General Merchandise (Grocery, Frozen, Beverages, etc.): Promo-driven,
    stable demand, longer shelf life
  - Hardware: Seasonal (spring renovation), durable goods, low frequency

Data volume per tier (~42 products × 15 stores × 730 days ≈ 460K rows)
is sufficient for independent model training.

Usage:
    from ml.segmentation import get_category_tier, get_tier_categories

    tier = get_category_tier("Produce")       # → "fresh"
    cats = get_tier_categories("fresh")        # → ["Produce", "Dairy", ...]
"""

from typing import Literal

CategoryTier = Literal["fresh", "general_merchandise", "hardware"]

CATEGORY_TIERS: dict[str, CategoryTier] = {
    # Fresh — perishable, short shelf life, weather-sensitive
    "Produce": "fresh",
    "Dairy": "fresh",
    "Bakery": "fresh",
    "Meat & Seafood": "fresh",
    # General Merchandise — promo-driven, stable demand
    "Grocery": "general_merchandise",
    "Frozen": "general_merchandise",
    "Beverages": "general_merchandise",
    "Household": "general_merchandise",
    "Health & Beauty": "general_merchandise",
    "Pet Supplies": "general_merchandise",
    "Baby": "general_merchandise",
    # Hardware — seasonal, durable, low frequency
    "Hardware": "hardware",
}

TIER_TO_CATEGORIES: dict[CategoryTier, list[str]] = {
    "fresh": ["Produce", "Dairy", "Bakery", "Meat & Seafood"],
    "general_merchandise": [
        "Grocery",
        "Frozen",
        "Beverages",
        "Household",
        "Health & Beauty",
        "Pet Supplies",
        "Baby",
    ],
    "hardware": ["Hardware"],
}

ALL_TIERS: list[CategoryTier] = ["fresh", "general_merchandise", "hardware"]


def get_category_tier(category: str) -> CategoryTier:
    """
    Map a product category to its model tier.

    Args:
        category: Department name (e.g., "Produce", "Grocery")

    Returns:
        Tier string: "fresh", "general_merchandise", or "hardware"

    Raises:
        ValueError if category is unknown.
    """
    tier = CATEGORY_TIERS.get(category)
    if tier is None:
        raise ValueError(f"Unknown category '{category}'. Known: {list(CATEGORY_TIERS.keys())}")
    return tier


def get_tier_categories(tier: CategoryTier) -> list[str]:
    """
    Get all categories belonging to a tier.

    Args:
        tier: One of "fresh", "general_merchandise", "hardware"

    Returns:
        List of category names.
    """
    categories = TIER_TO_CATEGORIES.get(tier)
    if categories is None:
        raise ValueError(f"Unknown tier '{tier}'. Known: {ALL_TIERS}")
    return categories.copy()


def get_model_name(tier: CategoryTier) -> str:
    """
    Get the MLflow experiment / model registry name for a tier.

    Examples:
        "fresh" → "demand_forecast_fresh"
        "general_merchandise" → "demand_forecast_gm"
        "hardware" → "demand_forecast_hardware"
    """
    short_names = {
        "fresh": "fresh",
        "general_merchandise": "gm",
        "hardware": "hardware",
    }
    return f"demand_forecast_{short_names[tier]}"
