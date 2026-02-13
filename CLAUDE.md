# Claude Code Project Instructions

## Git Workflow

- **Always create a PR** instead of merging directly to main
- After completing work on a phase branch, create a pull request using `gh pr create`
- The user will run a separate review and merge the PR themselves
- Never merge branches directly with `git merge`

## Development Practices

- Follow TDD: write tests first, then implement
- Run full test suite before committing: `uv run pytest tests/ -v`
- Use ruff for linting: `uv run ruff check`
- Commit messages follow conventional commits (feat:, fix:, docs:, etc.)

## Project Structure

- Virtual environment: `.venv/`
- Tests: `tests/`
- Application code: `app/`
- Specifications: `specs/`
- Research scripts: `research/`
