.PHONY: install run eval test smoke lint format typecheck clean

install:
	uv sync --extra dev
	uv run pre-commit install

run:
	uv run python -m src.pipeline
	@echo "--- running smoke tests against fixture domains ---"
	$(MAKE) smoke

eval:
	uv run python -m evals.run_eval

test:
	uv run pytest -m "not smoke"

smoke:
	uv run pytest -m smoke -v

lint:
	uv run ruff check src tests
	uv run black --check src tests

format:
	uv run black src tests
	uv run ruff check --fix src tests

typecheck:
	uv run mypy src

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build runs
	find . -type d -name __pycache__ -exec rm -rf {} +
