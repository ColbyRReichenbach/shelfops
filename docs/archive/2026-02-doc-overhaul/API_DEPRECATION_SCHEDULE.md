# API Deprecation Schedule

_Last updated: February 15, 2026_

## Canonical API Namespace

- Canonical namespace: `/api/v1/ml/*`

## Legacy Compatibility Aliases

Temporary aliases are active via middleware and return deprecation headers:

- `/ml/*` -> `/api/v1/ml/*`
- `/models/*` -> `/api/v1/ml/models/*`
- `/anomalies/*` -> `/api/v1/ml/anomalies/*`

## Deprecation Headers

Legacy responses include:

- `Deprecation: true`
- `Sunset: Wed, 30 Jun 2026 00:00:00 GMT`
- `X-API-Deprecated: Use /api/v1/ml/* endpoints`
- `Link: <canonical-path>; rel="successor-version"`

## Removal Date

- Target legacy alias removal date: **June 30, 2026**

## Consumer Migration Checklist

1. Move all ML route calls to `/api/v1/ml/*`.
2. Verify no service depends on `/ml/*`, `/models/*`, or `/anomalies/*`.
3. Remove legacy alias middleware after sunset date.
