PHONY: help doc

MAIN=$(shell basename $(PWD))

help: ## This help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

FDB_CLIENT="https://github.com/apple/foundationdb/releases/download/7.3.69/foundationdb-clients_7.3.69-1_amd64.deb"
FDB_SERVER="https://github.com/apple/foundationdb/releases/download/7.3.69/foundationdb-server_7.3.69-1_amd64.deb"

debian: ## Install foundationdb, requires sudo
	rm -rf fdb-clients.deb fdb-server.deb
	wget -q $(FDB_CLIENT) -O fdb-clients.deb
	dpkg -i fdb-clients.deb
	wget -q $(FDB_SERVER) -O fdb-server.deb
	dpkg -i fdb-server.deb

init: ## Prepare the host sytem for development
	pip install uv
	uv sync --all-extras --all-groups
	make hooks
	@echo "\033[95m\n\nYou may now run 'make check'.\n\033[0m"

hooks: ## Install git pre-commit and pre-push hooks
	@printf '#!/bin/sh\nmake check\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
	@printf '#!/bin/sh\nmake lint\n' > .git/hooks/pre-push && chmod +x .git/hooks/pre-push
	@echo "Installed .git/hooks/pre-commit (make check) and .git/hooks/pre-push (make lint)"

database-clear:
	fdbcli --exec "writemode on; clearrange \x00 \xFF;"

ITERATIONS?=1

check-correctness: ## Run binding tester correctness suite
	uv run bash scripts/setup_bindingtester.sh
	uv run bash scripts/run_bindingtester.sh $(ITERATIONS)

check: ## Run tests
	uv run python -m pytest -vvv --exitfirst --capture=no $(MAIN)/*.py
	uv run ruff check $(MAIN)

check-fast: ## Run tests, fail fast
	uv run python -m pytest -x -vvv --capture=no $(MAIN)

check-coverage: ## Code coverage
	uv run python -m pytest --quiet --cov-report=term --cov-report=html --cov=$(MAIN) $(MAIN)/*.py

lint: ## Lint the code
	uv run ruff check $(MAIN)

doc: ## Build the documentation
	cd doc && make html
	@echo "\033[95m\n\nBuild successful! View the docs homepage at doc/build/html/index.html.\n\032[0m"

clean: ## Clean up
	git clean -fX

todo: ## Things that should be done
	@grep -nR --color=always --before-context=2 --after-context=2 TODO $(MAIN)

xxx: ## Things that require attention
	@grep -nR --color=always --before-context=2 --after-context=2 XXX $(MAIN)

serve: ## Run the server
	uvicorn --reload --lifespan on --log-level warning --reload $(MAIN).vnstore:server

lock: ## Lock dependencies
	uv lock
	uv export --no-dev > requirements.txt
	uv export --only-group dev > requirements.dev.txt

cosmit: ## Format and auto-fix code
	uv run ruff format $(MAIN)
	uv run ruff check --fix $(MAIN)

wip: cosmit ## clean up code, and commit wip
	git add .
	git commit -m "wip"

release: ## Release package on pypi
	rm -rf dist
	make lock
	make init
	make check
	uv build --wheel
	uv publish dist/*
