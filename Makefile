.PHONY: install setup-sheet run run-demo mcp mcp-http mcp-demo eval eval-live eval-fixtures eval-calibration eval-report test smoke smoke-mcp lint format typecheck clean verify-public-repo provision-oracle deploy-oracle deploy-hf deploy-fly

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

mcp-http:
	uv run python -m src.mcp_server --transport http

mcp-demo:
	MCP_DEMO_MODE=1 uv run python -m src.mcp_server --transport http

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

# Primary target: Oracle Cloud Always Free (see docs/DEPLOY.md). Provisioning
# and redeploys happen against the VM itself, not from this machine's Docker
# build, so these targets wrap the oci CLI and SSH rather than a local push.
provision-oracle:
	bash deploy/oracle/provision.sh

deploy-oracle:
	@if [ -z "$(ORACLE_HOST)" ]; then \
		echo "Set ORACLE_HOST=<public-ip>.sslip.io, e.g. make deploy-oracle ORACLE_HOST=1.2.3.4.sslip.io" >&2; \
		exit 1; \
	fi
	ssh -o StrictHostKeyChecking=accept-new ubuntu@$(ORACLE_HOST) 'sudo bash -s' < deploy/oracle/setup.sh

# Alternatives, see docs/DEPLOY.md appendices (HF Docker Spaces now require a
# PRO subscription; Fly.io now requires a card on file for app creation).
deploy-hf:
	@if [ -z "$(HF_SPACE)" ]; then \
		echo "Set HF_SPACE=<owner>/<space-name>, e.g. make deploy-hf HF_SPACE=you/poc-scraper-mcp" >&2; \
		exit 1; \
	fi
	uv run python -m scripts.push_hf_space $(HF_SPACE)

# Pin exactly one machine after every deploy: the in-memory demo rate limits
# (per-IP + global daily cap) are only truly global with a single instance
# (HOST-06). fly.toml alone cannot express this; scale count is the mechanism.
deploy-fly:
	fly deploy --smoke-checks=false
	fly scale count 1 --yes
