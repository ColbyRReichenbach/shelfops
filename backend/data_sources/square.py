from __future__ import annotations

from typing import Any


def build_square_mapping_preview(
    *,
    locations: list[dict[str, Any]],
    catalog_items: list[dict[str, Any]],
    location_map: dict[str, str],
    catalog_map: dict[str, str],
    valid_store_ids: set[str],
    valid_product_ids: set[str],
) -> dict[str, Any]:
    location_rows = []
    unmapped_location_ids: list[str] = []
    mapped_locations = 0

    for location in locations:
        external_id = str(location.get("id", ""))
        mapped_store_id = location_map.get(external_id)
        is_valid_mapping = mapped_store_id in valid_store_ids if mapped_store_id else False
        status = "mapped" if is_valid_mapping else "unmapped"
        if status == "mapped":
            mapped_locations += 1
        elif external_id:
            unmapped_location_ids.append(external_id)
        location_rows.append(
            {
                "external_id": external_id,
                "name": location.get("name"),
                "status": status,
                "mapped_store_id": mapped_store_id if is_valid_mapping else None,
                "timezone": location.get("timezone"),
            }
        )

    catalog_rows = []
    unmapped_catalog_ids: list[str] = []
    mapped_catalog = 0

    for item in catalog_items:
        if item.get("type") != "ITEM":
            continue
        item_id = str(item.get("id", ""))
        item_data = item.get("item_data", {})
        variation_ids = [str(variation.get("id")) for variation in item_data.get("variations", []) if variation.get("id")]
        mapped_product_id = catalog_map.get(item_id)
        if not mapped_product_id:
            for variation_id in variation_ids:
                if variation_id in catalog_map:
                    mapped_product_id = catalog_map[variation_id]
                    break
        is_valid_mapping = mapped_product_id in valid_product_ids if mapped_product_id else False
        status = "mapped" if is_valid_mapping else "unmapped"
        if status == "mapped":
            mapped_catalog += 1
        elif item_id:
            unmapped_catalog_ids.append(item_id)
        catalog_rows.append(
            {
                "external_id": item_id,
                "name": item_data.get("name"),
                "variation_ids": variation_ids,
                "status": status,
                "mapped_product_id": mapped_product_id if is_valid_mapping else None,
            }
        )

    return {
        "locations": location_rows,
        "catalog_items": catalog_rows,
        "mapping_coverage": {
            "locations_total": len(location_rows),
            "locations_mapped": mapped_locations,
            "catalog_total": len(catalog_rows),
            "catalog_mapped": mapped_catalog,
        },
        "unmapped_location_ids": unmapped_location_ids,
        "unmapped_catalog_ids": unmapped_catalog_ids,
    }
