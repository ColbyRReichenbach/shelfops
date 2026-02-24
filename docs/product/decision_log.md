# ShelfOps Production Decision Log

- Last verified date: February 24, 2026
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

7. Ship-find-fix over speculative pre-engineering (`decided`)
- Rationale: AI-assisted iteration velocity has moved the crossover point where pre-engineering
  pays off significantly later. Unknown unknowns from real customer data are cheaper to fix on
  contact than to anticipate upfront. This applies specifically to: vertical generalization,
  domain-specific feature presets, edge cases in the optimizer, and schema variants outside
  current retail assumptions. None of these should be built until a real customer produces the
  need.
- Prerequisite before first onboarding: observability must be in place (error tracking with
  tenant context, structured logging, basic health metrics) so that "fix fast" is actually fast.
  Without it, the loop breaks — you can't fix what you can't see.
- What this does NOT defer: anything required for a reliable demo or for the retail SMB use
  case to work correctly end-to-end. The line is: don't over-engineer for customers you don't
  have yet, but don't under-build for the customer you are actively selling to.

