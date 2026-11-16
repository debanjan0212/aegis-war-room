.PHONY: install web serve demo test lint scan drill check lock

install:            ## install the backend, dev tools and the screen's libraries
	pip install -e ".[dev]"
	cd web && npm ci

web:                ## build the screen into web/dist
	cd web && npm run build

serve: web          ## start the war room on http://localhost:8000
	aegis serve

demo:               ## play one incident in the terminal, no browser or key needed
	aegis demo

test:
	pytest -q

lint:
	ruff check . && ruff format --check .

scan:               ## Code Guard agent: scan this repo for vulnerabilities
	aegis scan

drill:              ## attack the defences and check they hold
	aegis drill

check: lint test scan drill   ## everything CI runs. Do this before every push

lock:               ## refresh the hashed lock files after changing dependencies in pyproject.toml
	uv pip compile pyproject.toml --universal --generate-hashes -o requirements.lock
	uv pip compile pyproject.toml --extra cloud --universal --generate-hashes -o requirements-cloud.lock
