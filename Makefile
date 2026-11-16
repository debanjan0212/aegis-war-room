.PHONY: install web serve demo test lint scan drill check lock models shop shop-stop live drills

# Where the OpenTelemetry Demo shop lives: next to this folder unless you say otherwise (make shop SHOP=~/somewhere)
SHOP ?= ../opentelemetry-demo

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

models:             ## which models are set up, and does each one really answer
	aegis models --test

shop:               ## download (first time only) and start the OpenTelemetry Demo shop. Needs Docker
	@[ -d "$(SHOP)" ] || git clone --depth 1 https://github.com/open-telemetry/opentelemetry-demo.git "$(SHOP)"
	@extras="$(SHOP)/src/otel-collector/otelcol-config-extras.yml"; \
	if grep -qvE '^[[:space:]]*(#|$$)' "$$extras" 2>/dev/null; then echo "Keeping your own $$extras"; \
	else cp config/otel-demo-collector.yml "$$extras" && echo "Shop numbers will update every 15 seconds"; fi
	cd "$(SHOP)" && $(MAKE) start-minimal

shop-stop:          ## stop the shop and give the memory back
	cd "$(SHOP)" && $(MAKE) stop

live: web           ## the war room against the shop. It watches by itself and opens incidents
	AEGIS_SOURCE=otel-demo OTEL_DEMO_FLAG_FILE="$(abspath $(SHOP))/src/flagd/demo.flagd.json" \
	AEGIS_WATCH_EVERY=$${AEGIS_WATCH_EVERY:-20} AEGIS_VERIFY_TRIES=$${AEGIS_VERIFY_TRIES:-15} \
	AEGIS_VERIFY_WAIT=$${AEGIS_VERIFY_WAIT:-10} aegis serve

drills: web         ## the simulated incidents on port 8001, next to `make live`, with their own audit log
	AEGIS_SOURCE=simulator AEGIS_AUDIT_LOG=audit-drills.log.jsonl aegis serve --port 8001

lock:               ## refresh the hashed lock files after changing dependencies in pyproject.toml
	uv pip compile pyproject.toml --universal --generate-hashes -o requirements.lock
	uv pip compile pyproject.toml --extra cloud --universal --generate-hashes -o requirements-cloud.lock
