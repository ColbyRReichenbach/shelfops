# ShelfOps Production Decision Log

- Last verified date: February 15, 2026
- Audience: engineering leadership and reviewers
- Scope: durable architecture and release decisions
- Source of truth: this decision log

## Decisions

1. SMB-first launch path (`implemented`)
- Rationale: fastest path to operational proof and onboarding consistency.

2. Enterprise wording bounded to non-GA availability (`implemented`)
- Rationale: deterministic validation exists, but broad onboarding claims are not allowed.

3. Runtime loop before model-portfolio expansion (`implemented`)
- Rationale: reliability and measurable outcomes precede model-surface growth.

4. Promotion gate is fail-closed (`implemented`)
- Rationale: missing business metrics or insufficient evidence must block promotion.

5. Multi-tenant dispatch over hardcoded tenant scheduling (`implemented`)
- Rationale: supports production tenancy behavior.

6. Profile-driven contract boundary with explicit adapter escalation (`implemented`)
- Rationale: enables no-code onboarding for representable schema variants.
