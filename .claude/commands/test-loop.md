Run the test suite, analyze failures, fix them, and repeat until all tests pass.

**Step 1: Run tests**
```bash
PYTHONPATH=backend pytest backend/tests/ -v --tb=short 2>&1 | head -150
```

**Step 2: For each failing test**
- Read the test to understand what it expects
- Read the implementation code being tested
- Identify the root cause: implementation bug vs outdated test
- Fix the implementation if it is a real bug
- Update the test only if behavior has intentionally changed — confirm with me first

**Step 3: Re-run**
Run only the previously failing test to confirm fix, then run the full suite.

**Step 4: Report**
When all tests pass, summarize:
- How many tests were failing at start
- Root causes found (bug / stale test / missing fixture / import error)
- What was changed

Do not stop until all tests pass or you hit a blocker that requires my decision.
