Create a well-structured git commit for the current changes.

Steps:
1. Run `git diff --staged` and `git status` to see what is staged
2. If nothing is staged, show me `git status` and ask which files to stage
3. Write a commit message following Conventional Commits:
   - `feat:` new feature
   - `fix:` bug fix
   - `refactor:` code change without behavior change
   - `test:` adding or updating tests
   - `docs:` documentation
   - `chore:` build, config, or tooling
4. Subject line: imperative mood, max 72 characters, no period
5. Body (if needed): explain WHY, not what — wrap at 72 characters
6. Show me the proposed commit message and wait for confirmation before running `git commit`
