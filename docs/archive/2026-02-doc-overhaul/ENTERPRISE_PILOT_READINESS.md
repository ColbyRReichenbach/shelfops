# Enterprise Pilot Readiness

_Last updated: February 15, 2026_

## Positioning

ShelfOps enterprise track is **pilot-ready validation**, not broad production onboarding readiness.

## Source Order (Locked)

1. `EDI`
2. `SFTP`
3. `Event`

## Required Validation Gates

1. EDI fixture harness (`846/850/856/810`) parse -> persist -> audit assertions.
2. SFTP field mapping regression checks across inventory/transactions/products/stores.
3. Event schema validation and malformed replay tests.
4. Integration SLA regression checks on `/api/v1/integrations/sync-health`.

## CI Required Jobs

- `enterprise-seed-validation`
- `postgres-parity`
- `edi-fixture-e2e`
- `contract-validation-suite`

## Current Contract-Driven Interfaces

- Enterprise YAML profiles:
- `contracts/demo_enterprise/enterprise_edi/v1.yaml`
- `contracts/demo_enterprise/enterprise_sftp/v1.yaml`
- `contracts/demo_enterprise/enterprise_event/v1.yaml`

## Guardrail Language

Use this externally:

- “Enterprise integration architecture is implemented and under continuous pilot-style validation.”

Do not claim:

- general enterprise onboarding readiness without partner certification and live telemetry calibration.
