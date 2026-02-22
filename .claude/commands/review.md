Perform a code review on the changes in scope (files I name, or recently modified files).

**ShelfOps-Specific Checks**
- [ ] Authenticated routes use `get_tenant_db`, not `get_db`
- [ ] No hardcoded customer UUIDs (should use `DEV_CUSTOMER_ID` from `core.constants`)
- [ ] New tables have `customer_id` column
- [ ] Time-series splits are time-based, not `train_test_split(shuffle=True)`
- [ ] New Alembic migration created for any schema change
- [ ] TimescaleDB indexes excluded from autogenerate

**General Quality**
- [ ] No business logic in route handlers
- [ ] Pydantic models have `model_config = {"from_attributes": True}` where needed
- [ ] `async/await` used for all DB and I/O operations
- [ ] No `SELECT *` in production queries
- [ ] Correct HTTP status codes (201 create, 204 delete, not 200 for errors)

**ML-Specific**
- [ ] Pandera validation at all 3 pipeline gates
- [ ] MLflow run logged for any training execution
- [ ] `detect_feature_tier()` called — not hardcoded tier

For each issue found, state: file, line number, problem, and suggested fix. If no issues, confirm the review passed.
