.PHONY: help doc

FDB_CLIENT="https://github.com/apple/foundationdb/releases/download/6.3.22/foundationdb-clients_6.3.22-1_amd64.deb"
FDB_SERVER="https://github.com/apple/foundationdb/releases/download/6.3.22/foundationdb-server_6.3.22-1_amd64.deb"

help: ## This help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

init-foundationdb: ## Install foundationdb, requires sudo
	rm -rf fdb-clients.deb fdb-server.deb
	wget -q $(FDB_CLIENT) -O fdb-clients.deb
	dpkg -i fdb-clients.deb
	wget -q $(FDB_SERVER) -O fdb-server.deb
	dpkg -i fdb-server.deb

init: ## Prepare the host sytem for development
	poetry install
	@echo "\033[95m\n\nYou may now run 'make check'.\n\033[0m"

check: ## Run tests
	make database-clear
	pytest -vvv --capture=no tests.py
	bandit --skip=B101 -r found/

check-fast: ## Run tests, fail fast
	make database-clear
	pytest -x -vvv --capture=no tests.py

check-coverage: ## Code coverage
	make database-clear
	pytest --quiet --cov-report=term --cov-report=html --cov=found/ tests.py

lint: ## Lint the code
	pylama found/

doc: ## Build the documentation
	cd doc && make html
	@echo "\033[95m\n\nBuild successful! View the docs homepage at doc/build/html/index.html.\n\033[0m"

clean: ## Clean up
	git clean -fX

database-clear:  ## Remove all data from the database
	fdbcli --exec "writemode on; clearrange \x00 \xFF;"

todo: ## Things that should be done
	@grep -nR --color=always  --before-context=2  --after-context=2 TODO found/

xxx: ## Things that require attention
	@grep -nR --color=always --before-context=2  --after-context=2 XXX found/

release:  ## Prepare a release
	poetry publish --build
