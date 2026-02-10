"""
Square POS Integration Client

Handles API calls to Square for inventory sync.
Uses OAuth tokens stored in the integrations table.
"""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from core.config import get_settings
from core.security import decrypt

settings = get_settings()

SQUARE_BASE_URL = (
    "https://connect.squareupsandbox.com/v2"
    if settings.square_environment == "sandbox"
    else "https://connect.squareup.com/v2"
)


class SquareClient:
    """Client for Square API interactions."""

    def __init__(self, access_token_encrypted: str):
        self.access_token = decrypt(access_token_encrypted)
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Square-Version": "2024-01-18",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_locations(self) -> list[dict]:
        """Fetch all locations (stores) from Square."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SQUARE_BASE_URL}/locations",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json().get("locations", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_catalog(self, cursor: str | None = None) -> dict:
        """Fetch catalog items (products) from Square."""
        params = {"types": "ITEM"}
        if cursor:
            params["cursor"] = cursor
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SQUARE_BASE_URL}/catalog/list",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_inventory_counts(self, location_ids: list[str]) -> list[dict]:
        """Fetch inventory counts for given locations."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SQUARE_BASE_URL}/inventory/batch-retrieve-counts",
                headers=self.headers,
                json={"location_ids": location_ids},
            )
            response.raise_for_status()
            return response.json().get("counts", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_orders(
        self, location_ids: list[str], cursor: str | None = None
    ) -> dict:
        """Fetch orders (transactions) from Square."""
        body = {"location_ids": location_ids}
        if cursor:
            body["cursor"] = cursor
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SQUARE_BASE_URL}/orders/search",
                headers=self.headers,
                json=body,
            )
            response.raise_for_status()
            return response.json()


def map_location_to_store(location: dict, customer_id: str) -> dict:
    """Map a Square Location to a ShelfOps Store."""
    address = location.get("address", {})
    coords = location.get("coordinates", {})
    return {
        "customer_id": customer_id,
        "name": location.get("name", "Unknown"),
        "address": address.get("address_line_1"),
        "city": address.get("locality"),
        "state": address.get("administrative_district_level_1"),
        "zip_code": address.get("postal_code"),
        "lat": coords.get("latitude"),
        "lon": coords.get("longitude"),
        "timezone": location.get("timezone", "America/New_York"),
    }


def map_catalog_item_to_product(item: dict, customer_id: str) -> dict:
    """Map a Square CatalogObject to a ShelfOps Product."""
    item_data = item.get("item_data", {})
    variations = item_data.get("variations", [{}])
    first_variation = variations[0].get("item_variation_data", {}) if variations else {}
    price_money = first_variation.get("price_money", {})

    return {
        "customer_id": customer_id,
        "sku": first_variation.get("sku", item.get("id", "")),
        "name": item_data.get("name", "Unknown"),
        "category": item_data.get("category_id"),
        "unit_price": price_money.get("amount", 0) / 100 if price_money.get("amount") else None,
    }
