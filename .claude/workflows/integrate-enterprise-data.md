---
description: How to set up enterprise data integrations (EDI, SFTP, Kafka)
---

# Workflow: Integrate Enterprise Data Source

**Purpose**: Connect ShelfOps to enterprise retailer data systems
(EDI X12, SFTP batch files, Kafka event streams)

**Agent**: data-engineer

**Duration**: 2-4 hours per integration type

**Prerequisites**:
- Database running with updated schema (GTIN/UPC fields on products)
- Docker services up (`docker compose up -d`)
- Enterprise integration adapters deployed (`backend/integrations/`)

---

## Steps

### 1. Choose Integration Type

| Type | Protocol | Use Case | Retailer Example |
|------|----------|----------|-----------------|
| EDI X12 | SFTP + flat file | Traditional enterprise | Target, Walmart |
| SFTP Batch | CSV/TSV files | Mid-market + enterprise | Regional chains |
| Kafka/Pub/Sub | Event streaming | Modern enterprise | Lowe's, digital-first |
| REST API | HTTP | SMB POS systems | Square, Shopify |

### 2. Configure the Integration

```python
# Create integration record in database
from integrations.base import IntegrationType, get_adapter

# EDI example
config = {
    "edi_input_dir": "/data/edi/inbound",
    "edi_output_dir": "/data/edi/outbound",
    "edi_archive_dir": "/data/edi/archive",
    "partner_id": "TARGET_CORP",
    "edi_types": ["846", "856", "810"],
}
adapter = get_adapter(IntegrationType.EDI, customer_id="...", config=config)

# SFTP example
config = {
    "sftp_host": "sftp.retailer.com",
    "sftp_port": 22,
    "sftp_username": "shelfops_svc",
    "sftp_key_path": "/keys/retailer_rsa",
    "remote_dir": "/outbound/inventory",
    "local_staging_dir": "/data/sftp/staging",
    "file_patterns": {
        "inventory": "INV_SNAPSHOT_*.csv",
        "transactions": "DAILY_SALES_*.csv",
    },
}

# Kafka example
config = {
    "broker_type": "kafka",
    "bootstrap_servers": "localhost:9092",
    "topics": {
        "transactions": "pos.transactions.completed",
        "inventory": "inventory.adjustments",
    },
    "consumer_group": "shelfops-ingest",
}
```

### 3. Test Connection

```python
connected = await adapter.test_connection()
assert connected, "Connection failed — check config and credentials"
```

### 4. Run Initial Sync

```python
# Sync inventory first (usually the most data)
result = await adapter.sync_inventory()
print(f"Processed: {result.records_processed}, Failed: {result.records_failed}")

# Then products, transactions, stores
await adapter.sync_products()
await adapter.sync_transactions()
await adapter.sync_stores()
```

### 5. Set Up Scheduled Sync (Celery)

```python
# workers/sync_tasks.py
from celery import shared_task
from integrations.base import get_adapter, IntegrationType

@shared_task
def sync_enterprise_data(customer_id: str, integration_type: str, config: dict):
    adapter = get_adapter(IntegrationType(integration_type), customer_id, config)
    asyncio.run(adapter.sync_inventory())
    asyncio.run(adapter.sync_transactions())

# Schedule in Celery Beat:
# - EDI/SFTP: Every 15 minutes for file polling
# - Kafka: Continuous consumer (separate worker)
```

### 6. Verify Data in Database

```sql
-- Check products have GTINs
SELECT count(*) FROM products WHERE gtin IS NOT NULL;

-- Check EDI audit log
SELECT edi_type, status, records_processed, received_at
FROM edi_transaction_log
ORDER BY received_at DESC
LIMIT 10;

-- Check recent inventory levels
SELECT p.name, il.quantity_on_hand, il.timestamp
FROM inventory_levels il
JOIN products p ON il.product_id = p.product_id
ORDER BY il.timestamp DESC
LIMIT 20;
```

---

## Generating Test Data

Before connecting a real retailer, generate synthetic enterprise data:

```bash
# Generate full enterprise dataset (500 products, 15 stores, 365 days)
// turbo
python scripts/seed_enterprise_data.py

# Generate smaller dataset for quick testing
// turbo
python scripts/seed_enterprise_data.py --products 50 --stores 5 --days 30

# Download real Kaggle datasets for ML training
python scripts/download_kaggle_data.py --dataset favorita --preprocess
```

---

## Checklist

- [ ] Integration type selected
- [ ] Config created with correct credentials
- [ ] Connection test passes
- [ ] Initial sync completes successfully
- [ ] Data appears correctly in database
- [ ] Scheduled sync configured in Celery
- [ ] EDI transaction log recording documents (if EDI)
- [ ] GTINs/UPCs populated on products
- [ ] Monitoring alerts set for sync failures

---

## Troubleshooting

**Issue**: EDI files not being picked up
**Fix**: Check `edi_input_dir` path exists and has read permissions

**Issue**: SFTP connection timeout
**Fix**: Verify SSH key permissions (`chmod 600`), check firewall

**Issue**: Kafka consumer lag growing
**Fix**: Increase `max_poll_records`, add more consumer instances

**Issue**: CSV field mapping errors
**Fix**: Check column names in source file match `field_mappings` config

---

**Last Updated**: 2026-02-09
