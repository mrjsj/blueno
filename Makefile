.PHONY: blueno ty test lint format pre-commit docs pr

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
	@{ \
	  uv run blueno run --project-dir examples/jaffle_shop --concurrency 4; \
	  cat blueno.log; \
	  status=$$?; \
	  rm -rf jaffle_shop; \
	  exit $$status; \
	}


test-contoso:
	@{ \
	  uv run blueno run --project-dir examples/contoso --concurrency 4; \
	  cat blueno.log; \
	  status=$$?; \
	  rm -rf contoso; \
	  exit $$status; \
	}

pr:
	@branch=$$(git symbolic-ref --short HEAD); \
	type=$$(echo $$branch | cut -d'/' -f1); \
	desc=$$(echo $$branch | cut -d'/' -f2- | tr '-' ' '); \
	title="$$type: $$desc"; \
	echo "Enter PR body (end with Ctrl+D):"; \
	body=$$(cat); \
	git push --set-upstream origin $$branch; \
	gh pr create --base main --head $$branch --title "$$title" --body "$$body"; \
	while true; do \
		sleep 5; \
		run=$$(gh run list -b $$branch --limit 1 --json status,conclusion --jq '.[0]'); \
		status=$$(echo $$run | jq -r '.status'); \
		conclusion=$$(echo $$run | jq -r '.conclusion'); \
		if [ "$$status" = "completed" ]; then \
			if [ "$$conclusion" = "success" ]; then \
				echo "Workflow succeeded. Merging PR ..."; \
				git fetch origin; \
				git rebase origin/main; \
				git checkout main; \
				git pull origin main; \
				git merge $$branch --ff-only; \
				git push origin main; \
				git branch -d $$branch; \
				git push origin --delete $$branch || true; \
				break; \
			else \
				echo "Workflow failed."; \
				exit 1; \
			fi; \
		else \
			echo "Workflow still running ..."; \
			sleep 5; \
		fi; \
	done

check-pr:
	@branch=$$(git symbolic-ref --short HEAD); \
	while true; do \
		run=$$(gh run list -b $$branch --limit 1 --json status,conclusion --jq '.[0]'); \
		status=$$(echo $$run | jq -r '.status'); \
		conclusion=$$(echo $$run | jq -r '.conclusion'); \
		if [ "$$status" = "completed" ]; then \
			if [ "$$conclusion" = "success" ]; then \
				echo "Workflow succeeded. Merging PR ..."; \
				git fetch origin; \
				git rebase origin/main; \
				git checkout main; \
				git pull origin main; \
				git merge $$branch --ff-only; \
				git push origin main; \
				git branch -d $$branch; \
				git push origin --delete $$branch || true; \
				break; \
			else \
				echo "Workflow failed."; \
				exit 1; \
			fi; \
		else \
			echo "Workflow still running ..."; \
			sleep 5; \
		fi; \
	done	

release:
	@echo "Current tags:"
	@git tag | sort -V | tail -n 5
	@latest_tag=$$(git tag | sort -V | tail -n 1); \
	if [ -z "$$latest_tag" ]; then \
		latest_tag="v0.0.0"; \
	fi; \
	echo "Latest tag: $$latest_tag"; \
	echo "Select version bump:"; \
	echo "1) major"; \
	echo "2) minor"; \
	echo "3) patch"; \
	read -p "Enter choice [1-3]: " choice; \
	case $$choice in \
		1) bump="major" ;; \
		2) bump="minor" ;; \
		3) bump="patch" ;; \
		*) echo "Invalid choice." && exit 1 ;; \
	esac; \
	ver=$$(echo $$latest_tag | sed 's/^v//' ); \
	set -- $$(echo $$ver | tr '.' ' '); \
	major=$$1; minor=$$2; patch=$$3; \
	case $$bump in \
		major) major=$$((major + 1)); minor=0; patch=0 ;; \
		minor) minor=$$((minor + 1)); patch=0 ;; \
		patch) patch=$$((patch + 1)) ;; \
	esac; \
	new_tag="v$$major.$$minor.$$patch"; \
	echo "New tag will be: $$new_tag"; \
	read -p "Confirm tag creation and push? (y/N) " confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		echo "Aborted."; \
		exit 1; \
	fi; \
	git tag $$new_tag && git push origin $$new_tag


