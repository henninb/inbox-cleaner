# Repository Guidelines

## Project Structure & Module Organization
- `inbox_cleaner/`: Source package (`auth.py`, `extractor.py`, `database.py`, `cli.py`, engines, analyzers).
- `tests/`: Pytest suite (unit, integration). See markers in `pytest.ini`.
- Top-level scripts: `real_demo.py`, `demo.py`, `setup_credentials.py`, `diagnose_issues.py`.
- Config: `config.yaml.example` (copy to `config.yaml`). DB: `inbox_cleaner.db`.

## Build, Test, and Development Commands
- Install (dev): `pip install -e .[dev]`
- Run tests: `pytest` or `python -m pytest -v`
- Coverage (90% gate): `pytest --cov=inbox_cleaner --cov-report=term-missing`
- Lint: `flake8 inbox_cleaner tests`
- Format: `black .`
- Type check: `mypy inbox_cleaner`
- CLI: `inbox-cleaner --help` (entry point via `pyproject.toml`)
- Demos: `python real_demo.py --auth|--extract 50|--stats`

## Coding Style & Naming Conventions
- Python 3.9+. 4‑space indentation; no tabs.
- Formatting: Black (line length 88). Run before committing.
- Linting: Flake8 clean. Prefer type hints; keep `mypy` strict happy.
- Naming: `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- Structure: Keep modules inside `inbox_cleaner/`; avoid large scripts—prefer small, testable functions.

## Testing Guidelines
- Framework: Pytest. Patterns from `pytest.ini`: files `test_*.py` or `*_test.py`, classes `Test*`, functions `test_*`.
- Markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow` (select via `-m`).
- Coverage: Maintain ≥90% (CI gate mirrored locally).
- Run specific tests: `pytest tests/test_extractor.py::TestExtractor::test_basic -v`.

## Commit & Pull Request Guidelines
- Commits: Use concise, present‑tense summaries. Prefer Conventional Commits, e.g. `feat(auth): refresh expired tokens` or `fix(db): handle missing index`.
- PRs: Include scope/intent, linked issues, test plan, and relevant screenshots or sample CLI output. Keep diffs focused and covered by tests.
- Passing checks required: lint, format, type check, tests with coverage.

## Security & Configuration Tips
- Never commit real `config.yaml` or tokens. Use `config.yaml.example` as a template.
- Run `python setup_credentials.py` to configure OAuth locally; restrict credentials to your account.
- Email content is not sent externally; keep DB files local and out of VCS (see `.gitignore`).

## Example Workflow
```
pip install -e .[dev]
black . && flake8 inbox_cleaner tests && mypy inbox_cleaner
pytest -m "not slow" --cov=inbox_cleaner
inbox-cleaner diagnose
```
