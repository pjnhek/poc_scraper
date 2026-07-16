.PHONY: install setup-sheet run run-demo mcp eval eval-live eval-fixtures eval-calibration eval-report test smoke smoke-mcp lint format typecheck clean verify-public-repo

install:
	uv sync --extra dev
	uv run pre-commit install

setup-sheet:
	uv run python -m scripts.setup_sheet

run:
	uv run python -m src.pipeline

run-demo:
	DEMO_BUNDLE=fixtures/demo-bundle uv run python -m src.pipeline

mcp:
	uv run python -m src.mcp_server

eval: eval-live

eval-live:
	uv run python -m evals.run_live

eval-fixtures:
	uv run python -m evals.run_eval

eval-calibration:
	uv run python -m evals.run_eval --calibration

eval-report:
	uv run python -m evals.report

test:
	uv run pytest -m "not smoke"

smoke:
	uv run pytest -m smoke -v

smoke-mcp:
	uv run pytest tests/smoke/test_mcp_e2e.py -v

lint:
	uv run ruff check src tests evals
	uv run black --check src tests evals

format:
	uv run black src tests evals
	uv run ruff check --fix src tests evals

typecheck:
	uv run mypy src evals

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build runs
	find . -type d -name __pycache__ -exec rm -rf {} +

verify-public-repo:
	uv run python -m scripts.verify_public_repo
