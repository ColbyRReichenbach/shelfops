# Production Decision Log

_Last updated: February 15, 2026_

## Decision 001: SMB-First Launch Path

- Decision: prioritize SMB/mid-market launch-candidate workflows.
- Why: shorter onboarding cycle, faster validation of decision utility, lower integration dependency risk.
- Tradeoff: enterprise breadth deferred to pilot-validation framing.

## Decision 002: Enterprise Positioning Bound

- Decision: use “pilot-validation” wording for enterprise integration status.
- Why: current evidence is fixture-driven and deterministic, not broad customer onboarding at scale.
- Tradeoff: avoids over-claiming enterprise readiness.

## Decision 003: Runtime Loop Completion Before New Models

- Decision: build train -> forecast -> accuracy -> promotion loop before expanding model families.
- Why: production value depends on runtime reliability and measurable outcomes, not model count.
- Tradeoff: slower model-family expansion in short term.

## Decision 004: Promotion Gate is Fail-Closed

- Decision: block promotion on missing business metrics or insufficient accuracy sample windows.
- Why: avoids unsafe auto-promotion with low evidence quality.
- Tradeoff: fewer automatic promotions early in tenant lifecycle.

## Decision 005: Multi-Tenant Dispatch Over Fixed Tenant Scheduling

- Decision: dispatch scheduled jobs by active/trial tenant set.
- Why: removes hardcoded dev-tenant coupling and supports production tenancy.
- Tradeoff: requires stronger queue observability and per-tenant failure handling.

## Decision 006: Profile-Driven Contract Boundary

- Decision: representable schema differences are handled in YAML contract profiles; non-representable patterns emit `requires_custom_adapter`.
- Why: supports no-code onboarding for common cases while keeping boundaries explicit.
- Tradeoff: nested/complex source semantics still require adapter code.
