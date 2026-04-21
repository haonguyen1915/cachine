.PHONY: install
install:
	@echo "🚀 Installing environment"
	poetry install --with dev


.PHONY: publish
publish:
	@echo "🚀 Publishing package"
	poetry publish --build
.PHONY: lint
lint:
	@echo "🚀 Checking poetry.lock file"
	poetry check --lock
	@echo "🚀 Linting with ruff"
	poetry run ruff check
	@echo "🚀 Checking with pylint"
	PYLINTHOME=.pylint_cache poetry run pylint cachine
	@echo "🚀 Checking with mypy"
	@if poetry run python -c "import mypy" >/dev/null 2>&1; then \
		poetry run mypy cachine ; \
	elif command -v mypy >/dev/null 2>&1; then \
		mypy cachine ; \
	else \
		echo "⚠️  mypy not installed; skipping type check" ; \
	fi
	@echo "🟢 All checks have passed"

.PHONY: lint_test
lint_test:
	@echo "🚀 Checking poetry.lock file"
	poetry check --lock
	@echo "🚀 Linting with ruff"
	poetry run ruff check
	@echo "🚀 Checking with pylint"
	@echo "🚀 Checking with mypy"
	@if poetry run python -c "import mypy" >/dev/null 2>&1; then \
		poetry run mypy tests ; \
	elif command -v mypy >/dev/null 2>&1; then \
		mypy tests ; \
	else \
		echo "⚠️  mypy not installed; skipping type check" ; \
	fi
	@echo "🟢 All checks have passed"

.PHONY: fix
fix:
	@echo "🚀 Fixing with ruff"
	poetry run ruff check --fix cachine
	poetry run ruff check --fix tests

.PHONY: format
format:
	poetry run ruff format

.PHONY: test
test:
	@echo "🚀 Running tests with pytest"
	poetry run pytest tests

.PHONY: clean
clean:
	@echo "🧹 Removing Python bytecode and tool caches"
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyd' \) -delete
	rm -rf .pytest_cache .ruff_cache .mypy_cache .pylint_cache .cache
	rm -rf build dist *.egg-info
	find . -type f \( -name '*.db' -o -name '*.db-journal' -o -name '*.db-wal' -o -name '*.db-shm' \) -delete
	@echo "🟢 Clean done"
