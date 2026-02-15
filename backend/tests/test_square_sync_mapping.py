import uuid

from workers.sync import (
    _build_square_id_map,
    _resolve_external_uuid,
    _should_synthesize_square_demo_mappings,
    _synthesize_square_id_map,
)


def test_build_square_id_map_filters_invalid_values():
    parsed = _build_square_id_map(
        {
            "loc_a": "00000000-0000-0000-0000-000000000010",
            "loc_b": "not-a-uuid",
            "loc_c": None,
        }
    )
    assert parsed == {"loc_a": uuid.UUID("00000000-0000-0000-0000-000000000010")}


def test_resolve_external_uuid_prefers_mapping_then_uuid_fallback():
    mapping = {"sq_loc_1": uuid.UUID("00000000-0000-0000-0000-000000000011")}
    assert _resolve_external_uuid("sq_loc_1", mapping) == uuid.UUID("00000000-0000-0000-0000-000000000011")
    assert _resolve_external_uuid("00000000-0000-0000-0000-000000000012", mapping) == uuid.UUID(
        "00000000-0000-0000-0000-000000000012"
    )
    assert _resolve_external_uuid("plain-text", mapping) is None


def test_should_synthesize_square_demo_mappings_honors_global_or_integration_flags():
    class _Settings:
        square_enable_demo_id_synthesis = False

    assert _should_synthesize_square_demo_mappings(_Settings(), {}) is False
    assert _should_synthesize_square_demo_mappings(_Settings(), {"square_synthesize_demo_mappings": True}) is True

    _Settings.square_enable_demo_id_synthesis = True
    assert _should_synthesize_square_demo_mappings(_Settings(), {}) is True


def test_synthesize_square_id_map_assigns_deterministically_and_keeps_existing():
    existing = {"loc_a": uuid.UUID("00000000-0000-0000-0000-000000000021")}
    mapped = _synthesize_square_id_map(
        external_ids={"loc_b", "loc_c", "loc_a"},
        valid_internal_ids={
            "00000000-0000-0000-0000-000000000021",
            "00000000-0000-0000-0000-000000000022",
        },
        existing_mapping=existing,
    )
    assert mapped["loc_a"] == uuid.UUID("00000000-0000-0000-0000-000000000021")
    assert mapped["loc_b"] == uuid.UUID("00000000-0000-0000-0000-000000000021")
    assert mapped["loc_c"] == uuid.UUID("00000000-0000-0000-0000-000000000022")
