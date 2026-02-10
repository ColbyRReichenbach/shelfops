---
description: How to connect Square or Shopify POS for real-time transactions
---

# Workflow: Integrate POS System (SMB Tier)

**Purpose**: Connect Square/Shopify POS for real-time transactions

**Agent**: data-engineer

**Duration**: 3-4 hours

> **Note**: For enterprise integrations (EDI X12, SFTP, Kafka), see
> `integrate-enterprise-data.md` instead.

---

## Steps

### 1. Implement OAuth Flow
- Create OAuth endpoints (`/connect`, `/callback`)
- Exchange code for access token
- Store encrypted tokens in database
- Set `integration_type = 'rest_api'` on the integration record

### 2. Set Up Webhooks
- Register webhook URL with provider
- Implement signature verification
- Create webhook handler endpoint

### 3. Map External Schema to ShelfOps
- Location → Store mapping
- CatalogObject/Variant → Product mapping (include `upc` field)
- Order → Transactions mapping

### 4. Test Integration
- Connect test account
- Trigger test transaction
- Verify data appears in database

---

**Checklist**:
- [ ] OAuth flow implemented
- [ ] Webhooks configured
- [ ] Data mapping complete (including UPC/GTIN when available)
- [ ] Test transaction successful
- [ ] `integration_type` set correctly on integration record

**Last Updated**: 2026-02-09
