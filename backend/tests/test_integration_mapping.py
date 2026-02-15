from integrations.event_adapter import validate_event
from integrations.sftp_adapter import FlatFileParser


def test_sftp_csv_mapping_regression():
    content = "ITEM_NBR,STORE_NBR,QTY_SOLD,TRANS_DATE\nSKU1,STR1,5,2026-01-01\n"
    mapping = {
        "ITEM_NBR": "product_id",
        "STORE_NBR": "store_id",
        "QTY_SOLD": "quantity",
        "TRANS_DATE": "date",
    }
    rows = FlatFileParser.parse_csv(content, delimiter=",", field_mapping=mapping)
    assert rows == [{"product_id": "SKU1", "store_id": "STR1", "quantity": "5", "date": "2026-01-01"}]


def test_event_schema_rejects_malformed_message():
    malformed = {"event_id": "e1", "timestamp": "2026-01-01T00:00:00Z"}
    schema = {"required_fields": ["event_id", "store_id", "timestamp", "items"]}
    errors = validate_event(malformed, schema)
    assert "Missing required field: store_id" in errors
    assert "Missing required field: items" in errors
