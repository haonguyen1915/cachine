# Repository Guidelines

## Project Structure & Module Organization
- `cachine/` – Library source
  - `backends/` (inmemory, redis sync/async, cluster, sentinel)
  - `decorators/` (`cached`), `middleware/` (metrics, fail-open), `serializers/`, `utils/`
- `tests/` – Pytest suite (unit, integration, performance). Redis tests are opt‑in.
- `examples/` – Quick usage samples.
- `README.md` – Usage and troubleshooting. `Makefile` – common tasks.

## Build, Test, and Development Commands
- `make install` – Install deps with Poetry (dev included).
- `make lint` – Ruff, pylint, and mypy on `cachine/`.
- `make lint_test` – Ruff, pylint (tests), mypy (tests chilled by config).
- `make test` – Run the test suite (pytest).
- `make fix` – Auto‑fix with Ruff in `cachine/` and `tests/`.
- `make format` – Code formatting via `ruff format`.

Examples:
- Enable Redis tests: `RUN_REDIS_TESTS=1 poetry run pytest tests/unit/redis -q`
- Configure Redis via env: `CACHE_HOST=localhost CACHE_DB=0 ...`

Interpreter (required): Use the Anaconda env at `/Users/haonv/anaconda3/envs/py10/bin/python` for all Python execution. Examples:
- `/Users/haonv/anaconda3/envs/py10/bin/python -m pytest tests -q`
- `/Users/haonv/anaconda3/envs/py10/bin/python -m mypy cachine`
- Prefer `conda run -n py10 <command>` when composing longer commands.

## Coding Style & Naming Conventions
- Python ≥ 3.10 with type hints. Keep public APIs typed.
- Lint/format: Ruff (PEP8 + rules), Pylint (library strict, tests relaxed), Mypy (strict for `cachine/`).
- Prefer descriptive names; avoid one‑letter variables; short functions where possible.
- Follow existing module layout; keep changes minimal and targeted.

## Testing Guidelines
- Framework: `pytest`; `pytest-asyncio` optional for async Redis tests.
- Naming: `tests/<area>/test_*.py`; one behavior per test where feasible.
- Redis tests are skipped unless `RUN_REDIS_TESTS=1`; they expect a reachable Redis.

## Commit & Pull Request Guidelines
- Conventional Commits enforced (see `.releaser.toml`): `feat:`, `fix:`, `docs:`, `chore:`, etc.
- PRs should include: concise description, rationale, screenshots/logs if user‑facing, and test coverage for new behavior.
- Keep diffs focused; avoid unrelated refactors.

## Security & Configuration Tips
- Secrets via env only (e.g., `CACHE_PASSWORD`). Do not commit credentials.
- Timeouts supported for Redis: `socket_timeout`, `socket_connect_timeout`, `retry_on_timeout` (dict or env).
- For high availability, see Redis Sentinel/Cluster backends; for resilience, consider `FailOpenMiddleware`.

## Agent‑Specific Instructions
- Obey this AGENTS.md. When editing, prefer surgical patches and maintain style consistency.
- Validate with `make lint_test` before handing off. If you add public APIs, update `README.md` and tests.
 - When invoking Python, prefer the explicit interpreter: `/Users/haonv/anaconda3/envs/py10/bin/python`.
