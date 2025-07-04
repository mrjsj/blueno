.PHONY: blueno ty test lint format pre-commit docs

uv-sync:
	uv sync --all-extras --all-groups

blueno:
	uv run blueno

blueno-d:
	uv run blueno run --project-dir tests/blueprints/simple  --log-level DEBUG

blueno-q:
	uv run blueno run --log-level NONE

gen-data:
	./data_generator/DatabaseGenerator ./data_generator/config.json ./data_generator/data.xlsx  ./data_generator/out ./data_generator/cache

ty:
	uv run ty check src --error-on-warning

unit-test:
	uv run pytest -s -vvvv tests --ignore=tests/fuzz

docs-test:
	uv run pytest -s -vvvv --markdown-docs docs src

fuzz-test:
	uv run pytest -s -vvvv tests/fuzz

lint:
	uv run ruff check --fix

format:
	uv run ruff format

docs:
	cp -r assets/images/* docs/assets/images

serve-docs:
	uv run mkdocs serve -w src -w docs -w mkdocs.yml

run:
	uv run pytest -s -vvvv tests/blueprints/test_blueprints.py::test_blueprint_simple_example --doctest-modules

pre-commit:	lint format ty unit-test docs-test docs

test-jaffle:
	uv run blueno run --project-dir examples/jaffle_shop --concurrency 4
	rm -rf jaffle_shop

test-contoso:
	uv run blueno run --project-dir examples/contoso --concurrency 4
	rm -rf contoso
