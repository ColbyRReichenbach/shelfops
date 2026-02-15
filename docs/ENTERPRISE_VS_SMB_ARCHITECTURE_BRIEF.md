# Enterprise vs SMB Architecture Brief

_Last updated: February 15, 2026_

## Intent

Document how ShelfOps differs by market tier without overstating readiness.

## SMB (Primary Launch Target)

- Sources: CSV/SFTP first.
- Onboarding: profile-driven contract mapping (`contracts/<tenant>/<source>/v1.yaml`).
- Deployment objective: forecast + inventory decision workflows within days after validated mapping.
- Reliability expectation: strong deterministic internal tests + operational runbooks.

## Enterprise (Pilot-Validation Track)

- Source order: EDI -> SFTP -> Event.
- Validation depth: deterministic fixture and worker-path coverage for `846/850/856/810`.
- Reliability objective: pilot-style integration exercises and incident handling runbooks.
- Claim boundary: integration architecture is validated; broad onboarding GA is not claimed.

## Key Technical Differences

| Area | SMB | Enterprise |
|---|---|---|
| Data heterogeneity | Moderate | High |
| Contract complexity | Medium | High |
| SLA strictness | Medium | High |
| Auditability depth | Standard | Strict (document-level and workflow-level) |
| Rollout complexity | Lower | Higher |

## Shared Core

- Canonical model lifecycle governance (champion/challenger).
- Metrics contract for forecast evaluation.
- Tenant-isolated data model and worker orchestration.
- Truth-aligned readiness documentation.
