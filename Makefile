.PHONY: blueno ty test lint format pre-commit docs


blueno:
	uv run blueno

blueno-d:
	uv run blueno --debug

blueno-q:
	uv run blueno --quiet

ty:
	uv run ty check src --error-on-warning

test:
	uv run pytest -s -vvvv tests

lint:
	uv run ruff check --fix

format:
	uv run ruff format

docs:
	cp README.md docs/index.md
	cp -r assets/images/* docs/assets/images

serve-docs:
	uv run mkdocs serve

run:
	uv run pytest -s -vvvv tests/blueprints/test_blueprints.py::test_blueprint_simple_example

pre-commit:	lint format ty test docs