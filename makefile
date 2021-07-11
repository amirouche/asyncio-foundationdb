.PHONY: help doc

help: ## This help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

init: ## Prepare the host sytem for development
	rm -rf fdb-clients.deb fdb-server.deb
	wget https://www.foundationdb.org/downloads/6.3.15/ubuntu/installers/foundationdb-clients_6.3.15-1_amd64.deb -O fdb-clients.deb
	sudo dpkg -i fdb-clients.deb
	wget https://www.foundationdb.org/downloads/6.3.15/ubuntu/installers/foundationdb-server_6.3.15-1_amd64.deb -O fdb-server.deb
	sudo dpkg -i fdb-server.deb
	poetry install
	@echo "\033[95m\n\nYou may now run 'make check'.\n\033[0m"

check: ## Run tests
	make database-clear
	py.test -vvv --capture=no tests.py
	bandit --skip=B101 -r found/
	@echo "\033[95m\n\nYou may now run 'make lint' or 'make check-coverage'.\n\033[0m"

check-fast: ## Run tests, fail fast
	make database-clear
	py.test -x -vvv --capture=no tests.py


check-coverage: ## Code coverage
	make database-clear
	py.test -vv --cov-config .coveragerc --cov-report term --cov-report html --cov-report xml --cov=found/ tests.py


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
	@grep -nR --color=always TODO found/

xxx: ## Things that require attention
	@grep -nR --color=always --before-context=2  --after-context=2 XXX found/

release:  ## Prepare a release
	poetry publish --build
