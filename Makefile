VERSION := $(shell python -c 'import tomli; print(tomli.load(open("pyproject.toml", "rb"))["tool"]["poetry"]["version"])')
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
	poetry run pylint polycrud
	@echo "🚀 Checking with mypy"
	poetry run mypy polycrud
	@echo "🟢 All checks have passed"

.PHONY: lint_test
lint_test:
	@echo "🚀 Checking poetry.lock file"
	poetry check --lock
	@echo "🚀 Linting with ruff"
	poetry run ruff check
	@echo "🚀 Checking with pylint"
	poetry run pylint tests
	@echo "🚀 Checking with mypy"
	poetry run mypy tests
	@echo "🟢 All checks have passed"

.PHONY: fix
fix:
	@echo "🚀 Fixing with ruff"
	poetry run ruff check --fix polycrud
	poetry run ruff check --fix tests

.PHONY: format
format:
	poetry run ruff format

.PHONY: run
run:
	uvicorn polycrud.__main__:app --host 0.0.0.0 --port 8001



