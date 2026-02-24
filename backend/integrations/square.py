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
    async def _fetch_catalog_page(self, cursor: str | None = None) -> dict:
        """Fetch a single page of catalog items from Square.

        The @retry decorator is intentionally on this private helper so that
        transient failures on any individual page are retried without restarting
        the entire pagination loop.
        """
        params: dict[str, str] = {"types": "ITEM"}
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

    async def get_catalog(self) -> list[dict]:
        """Fetch ALL catalog items from Square, following cursor-based pagination.

        Square's catalog/list endpoint returns at most one page of objects per
        request.  When additional pages exist the response contains a ``cursor``
        field.  This method drives the pagination loop and returns the flat,
        accumulated list of every CatalogObject across all pages.

        Retry logic lives in ``_fetch_catalog_page`` so that transient errors on
        any single page are retried without restarting from page one.

        Returns:
            Flat list of raw CatalogObject dicts from every page.
        """
        all_objects: list[dict] = []
        cursor: str | None = None

        while True:
            page = await self._fetch_catalog_page(cursor)
            all_objects.extend(page.get("objects", []))
            cursor = page.get("cursor")
            if not cursor:
                break

        return all_objects

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_inventory_counts(self, location_ids: list[str]) -> list[dict]:
        """Fetch inventory counts for given locations."""
        body = {"location_ids": location_ids} if location_ids else {}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SQUARE_BASE_URL}/inventory/batch-retrieve-counts",
                headers=self.headers,
                json=body,
            )
            response.raise_for_status()
            return response.json().get("counts", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_orders(self, location_ids: list[str], cursor: str | None = None) -> list[dict]:
        """Fetch orders (transactions) from Square."""
        body = {"location_ids": location_ids} if location_ids else {}
        if cursor:
            body["cursor"] = cursor
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SQUARE_BASE_URL}/orders/search",
                headers=self.headers,
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("orders", [])


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
    """Map a Square CatalogObject to a ShelfOps Product.

    Handles two object types returned by the Square catalog API:
    - ITEM: top-level catalog item with item_data; SKU and price are taken from
      the first variation nested inside item_data.variations.
    - ITEM_VARIATION: standalone variation object with item_variation_data; SKU
      and price live directly in that sub-dict, and there is no item_data.name,
      so "Unknown" is used as the product name.
    """
    if item.get("type") == "ITEM_VARIATION":
        variation_data = item.get("item_variation_data", {})
        price_money = variation_data.get("price_money", {})
        return {
            "customer_id": customer_id,
            "sku": variation_data.get("sku", item.get("id", "")),
            "name": variation_data.get("name", "Unknown"),
            "category": None,
            "unit_price": price_money.get("amount", 0) / 100 if price_money.get("amount") else None,
        }

    # Default: ITEM type (or unrecognised type — treat as ITEM)
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


def build_variation_to_parent_map(catalog_items: list[dict]) -> dict[str, str]:
    """Build a mapping from variation ID to parent item ID.

    Square inventory counts reference catalog_object_id values that may point to
    an ITEM_VARIATION rather than its parent ITEM.  This map lets the sync worker
    resolve a variation ID back to the parent item ID so it can be looked up in
    the catalog_map (which is keyed on parent item IDs).

    Only ITEM-type objects are iterated; their nested variation objects each carry
    a top-level "id" field that becomes the key, and the parent item's "id" is the
    value.

    Args:
        catalog_items: Raw list of CatalogObject dicts as returned by the Square
            catalog/list endpoint.

    Returns:
        Dict mapping variation_id (str) -> parent_item_id (str).
    """
    variation_to_parent: dict[str, str] = {}
    for catalog_object in catalog_items:
        if catalog_object.get("type") != "ITEM":
            continue
        parent_id = catalog_object.get("id")
        if not parent_id:
            continue
        item_data = catalog_object.get("item_data", {})
        for variation in item_data.get("variations", []):
            variation_id = variation.get("id")
            if variation_id:
                variation_to_parent[variation_id] = parent_id
    return variation_to_parent
