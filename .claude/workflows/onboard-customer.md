# Workflow: Onboard Customer

**Purpose**: Set up new customer account and integrate their systems

**Agent**: data-engineer

**Duration**: 2-4 hours per customer

---

## Steps

### 1. Create Customer Account
```sql
INSERT INTO customers (customer_id, company_name, subscription_tier)
VALUES (gen_random_uuid(), 'Acme Retail', 'growth');
```

### 2. Import Store Locations
- Get store list from customer
- Import to `stores` table
- Verify addresses, coordinates

### 3. Import Product Catalog
- Get SKU list (CSV or API)
- Import to `products` table
- Validate UPCs, prices

### 4. Connect POS System
- Customer completes OAuth flow
- Test webhook delivery
- Verify transactions flowing

### 5. Run Initial Forecast
- Wait for 7 days of transaction data
- Train models
- Generate forecasts

---

**Checklist**:
- [ ] Customer account created
- [ ] Stores imported
- [ ] Products imported
- [ ] POS connected
- [ ] Transaction data flowing
- [ ] Models trained
- [ ] Forecasts generated

**Last Updated**: 2026-02-09
