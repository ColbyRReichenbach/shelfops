Diagnose and fix the error or unexpected behavior I describe.

Debugging process:
1. **Reproduce**: Identify the exact command, request, or condition that triggers the issue
2. **Locate**: Trace the code path (API route → service → DB/ML layer)
3. **Hypothesize**: List 2-3 likely root causes ranked by probability
4. **Verify**: Read the code for the most likely cause. Check `.claude/docs/errors.md` for similar past issues
5. **Fix**: Implement the minimal fix
6. **Test**: Run the relevant test(s) to confirm the fix works
7. **Document**: If non-obvious, add an entry to `.claude/docs/solutions.md`

Do not guess without reading the code. Do not add workarounds without understanding the root cause.
