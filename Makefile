.PHONY: help doc

init: ## Prepare the host sytem for development
	# install FoundationDB
	wget https://www.foundationdb.org/downloads/5.2.5/ubuntu/installers/foundationdb-clients_5.2.5-1_amd64.deb
	sudo dpkg -i foundationdb-clients_5.2.5-1_amd64.deb
	wget https://www.foundationdb.org/downloads/5.2.5/ubuntu/installers/foundationdb-server_5.2.5-1_amd64.deb
	sudo dpkg -i foundationdb-server_5.2.5-1_amd64.deb
	# Proceed with python dependencies
	pip3 install pipenv --upgrade
	pipenv install --dev --skip-lock
	pipenv run python setup.py develop
	pipenv run pre-commit install
	@echo "\033[95m\n\nYou may now run 'pipenv shell'.\n\033[0m"

check: ## Run tests
	pipenv run py.test -vv --capture=no tests.py
	make database-clear
	pipenv check
	bandit --skip=B101 -r src/
	@echo "\033[95m\n\nYou may now run 'make lint' or 'make coverage'.\n\033[0m"

coverage: ## Code coverage
	pipenv run py.test -vv --cov-config .coveragerc --cov-report term --cov-report html --cov-report xml --cov=found/ tests.py
	make database-clear

help: ## This help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

lint: ## Lint the code
	pipenv run pylint found/

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
	python setup.py sdist bdist_wheel
	@echo "\033[95m\n\nBuild successful! You can now run 'python setup.py sdist upload'.\n\033[0m"
