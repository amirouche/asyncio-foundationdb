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
	pip install poetry poetry-plugin-export
	poetry install
	@echo "\033[95m\n\nYou may now run 'make check'.\n\033[0m"

database-clear:
	fdbcli --exec "writemode on; clearrange \x00 \xFF;"

ITERATIONS?=1

check-correctness: ## Run binding tester correctness suite
	poetry run bash scripts/setup_bindingtester.sh
	poetry run bash scripts/run_bindingtester.sh $(ITERATIONS)

check: ## Run tests
	poetry run pytest -vvv --exitfirst --capture=no $(MAIN)/*.py
	if command -v bandit > /dev/null; then bandit --skip=B101,B311 -r $(MAIN); fi

check-fast: ## Run tests, fail fast
	pytest -x -vvv --capture=no $(MAIN)

check-coverage: ## Code coverage
	pytest --quiet --cov-report=term --cov-report=html --cov=$(MAIN) $(MAIN)/*.py

lint: ## Lint the code
	pylama $(MAIN)

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
	poetry lock
	poetry export > requirements.txt
	poetry export --only=dev > requirements.dev.txt

wip: ## clean up code, and commit wip
	black $(MAIN)
	isort --profile black $(MAIN)
	git add .
	git commit -m "wip"

release: ## Release package on pypi
	rm -rf dist
	make lock
	make init
	make check
	python3 -m build --wheel
	python3 -m twine upload dist/*
