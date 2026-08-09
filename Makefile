# TrainDash Makefile
#
# Common targets for development and testing
#
# Usage:
#   make dev        # Start local dev stack (builds from source)
#   make edge       # Start edge stack (latest main branch image)
#   make latest     # Start release stack (latest tagged release)
#   make e2e        # Start E2E test stack
#   make e2e-run    # Run E2E tests (starts stack if needed)
#   make down       # Stop any running stack
#   make clean      # Stop stack and remove volumes
#   make logs       # Tail logs from running stack

.PHONY: dev edge latest e2e e2e-run down clean logs help

# Default compose project name (prevents conflicts between stacks)
PROJECT_NAME ?= traindash

# Detect which stack is currently running
RUNNING_STACK := $(shell docker compose ls --format json 2>/dev/null | grep -o '"traindash[^"]*"' | tr -d '"' | head -1)

#------------------------------------------------------------------------------
# Stack management
#------------------------------------------------------------------------------

## Start local development stack (builds from source)
dev: _stop-other-stacks
	@echo "Starting dev stack (building from source)..."
	docker compose -p $(PROJECT_NAME)-dev -f compose/dev.yml up -d --build
	@echo "Dev stack running at http://localhost:8000"

## Start edge stack (latest main branch image from ghcr.io)
edge: _stop-other-stacks _pull-edge
	@echo "Starting edge stack..."
	docker compose -p $(PROJECT_NAME)-edge -f compose/edge.yml up -d
	@echo "Edge stack running at http://localhost:8000"

## Start latest release stack (latest tagged release from ghcr.io)
latest: _stop-other-stacks _pull-latest
	@echo "Starting latest release stack..."
	docker compose -p $(PROJECT_NAME)-latest -f compose/latest.yml up -d
	@echo "Latest stack running at http://localhost:8000"

## Start E2E test stack (port 8001, fresh DB)
e2e: _stop-other-stacks
	@echo "Starting E2E stack (building from source)..."
	docker compose -p $(PROJECT_NAME)-e2e -f compose/e2e.yml up -d --build
	@echo "E2E stack running at http://localhost:8001"
	@echo "Waiting for health check..."
	@timeout 120 bash -c 'until curl -sf http://localhost:8001/api/health > /dev/null; do sleep 2; done' && echo "Ready!"

## Run E2E tests (starts stack if needed, then runs Playwright)
e2e-run: e2e
	@echo "Running Playwright tests..."
	cd frontend && npx playwright test --project=setup --project=chromium --project=chromium-no-auth

## Stop any running stack
down:
	@echo "Stopping all traindash stacks..."
	-docker compose -p $(PROJECT_NAME)-dev -f compose/dev.yml down 2>/dev/null
	-docker compose -p $(PROJECT_NAME)-edge -f compose/edge.yml down 2>/dev/null
	-docker compose -p $(PROJECT_NAME)-latest -f compose/latest.yml down 2>/dev/null
	-docker compose -p $(PROJECT_NAME)-e2e -f compose/e2e.yml down 2>/dev/null
	@echo "All stacks stopped"

## Stop stack and remove volumes (clean slate)
clean:
	@echo "Stopping all traindash stacks and removing volumes..."
	-docker compose -p $(PROJECT_NAME)-dev -f compose/dev.yml down -v 2>/dev/null
	-docker compose -p $(PROJECT_NAME)-edge -f compose/edge.yml down -v 2>/dev/null
	-docker compose -p $(PROJECT_NAME)-latest -f compose/latest.yml down -v 2>/dev/null
	-docker compose -p $(PROJECT_NAME)-e2e -f compose/e2e.yml down -v 2>/dev/null
	@echo "All stacks stopped and volumes removed"

## Tail logs from the dev stack
logs:
	docker compose -p $(PROJECT_NAME)-dev -f compose/dev.yml logs -f

## Show logs for edge stack
logs-edge:
	docker compose -p $(PROJECT_NAME)-edge -f compose/edge.yml logs -f

## Show logs for E2E stack
logs-e2e:
	docker compose -p $(PROJECT_NAME)-e2e -f compose/e2e.yml logs -f

#------------------------------------------------------------------------------
# Testing shortcuts
#------------------------------------------------------------------------------

## Run backend unit tests
test-unit:
	cd backend && uv run pytest tests/unit/ -v

## Run backend integration tests
test-integration:
	cd backend && uv run pytest tests/integration/ -v

## Run frontend unit tests
test-frontend:
	cd frontend && npm test

## Run all tests (unit + integration + frontend)
test: test-unit test-integration test-frontend

#------------------------------------------------------------------------------
# Internal targets
#------------------------------------------------------------------------------

_stop-other-stacks:
	@# Stop any running traindash stacks before starting a new one
	@for stack in dev edge latest e2e; do \
		if docker compose -p $(PROJECT_NAME)-$$stack ps -q 2>/dev/null | grep -q .; then \
			echo "Stopping $(PROJECT_NAME)-$$stack..."; \
			docker compose -p $(PROJECT_NAME)-$$stack -f compose/$$stack.yml down; \
		fi; \
	done

_pull-edge:
	@echo "Pulling edge image..."
	docker pull ghcr.io/tomberch/training-dash:edge

_pull-latest:
	@echo "Pulling latest image..."
	docker pull ghcr.io/tomberch/training-dash:latest

#------------------------------------------------------------------------------
# Help
#------------------------------------------------------------------------------

## Show this help
help:
	@echo "TrainDash Makefile"
	@echo ""
	@echo "Stack targets:"
	@echo "  make dev        Start local dev stack (builds from source)"
	@echo "  make edge       Start edge stack (latest main branch image)"
	@echo "  make latest     Start release stack (latest tagged release)"
	@echo "  make e2e        Start E2E test stack (port 8001)"
	@echo "  make e2e-run    Run E2E tests"
	@echo "  make down       Stop any running stack"
	@echo "  make clean      Stop stack and remove volumes"
	@echo "  make logs       Tail logs from dev stack"
	@echo ""
	@echo "Test targets:"
	@echo "  make test-unit         Run backend unit tests"
	@echo "  make test-integration  Run backend integration tests"
	@echo "  make test-frontend     Run frontend tests"
	@echo "  make test              Run all tests"
