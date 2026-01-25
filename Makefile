# Sports Betting Model Development - Makefile
# Common commands for development workflow

.PHONY: help setup install test lint format clean db-init db-reset run-daily run-backtest docs

# Default target
help:
	@echo "Sports Betting Model Development - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup        - Full environment setup (conda + packages + database)"
	@echo "  make install      - Install Python dependencies only"
	@echo "  make db-init      - Initialize SQLite database"
	@echo "  make db-reset     - Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "Development:"
	@echo "  make test         - Run all tests"
	@echo "  make test-fast    - Run tests excluding slow ones"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo "  make lint         - Run linting checks"
	@echo "  make format       - Auto-format code"
	@echo "  make typecheck    - Run type checking"
	@echo ""
	@echo "Operations:"
	@echo "  make run-daily    - Run daily data refresh and predictions"
	@echo "  make run-backtest - Run backtesting suite"
	@echo "  make run-reconcile - Run evening reconciliation"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Remove temporary files and caches"
	@echo "  make backup       - Create database backup"
	@echo "  make docs         - Generate documentation"
	@echo ""

# =============================================================================
# Setup
# =============================================================================

setup:
	@echo "Running full environment setup..."
	bash scripts/setup_environment.sh

install:
	pip install --upgrade pip
	pip install -r requirements.txt

db-init:
	@echo "Initializing database..."
	mkdir -p data
	sqlite3 data/betting.db < scripts/init_database.sql
	@echo "Database initialized at data/betting.db"

db-reset:
	@echo "WARNING: This will delete all data in the database!"
	@read -p "Are you sure? (y/N): " confirm; \
	if [ "$$confirm" = "y" ]; then \
		rm -f data/betting.db; \
		sqlite3 data/betting.db < scripts/init_database.sql; \
		echo "Database reset complete."; \
	else \
		echo "Cancelled."; \
	fi

# =============================================================================
# Development
# =============================================================================

test:
	pytest tests/ -v

test-fast:
	pytest tests/ -v -m "not slow"

test-cov:
	pytest tests/ -v --cov=models --cov=betting --cov=tracking --cov-report=term-missing --cov-report=html:reports/coverage

test-model:
	pytest tests/ -v -m "model"

test-betting:
	pytest tests/ -v -m "betting"

lint:
	@echo "Running ruff linter..."
	ruff check models/ betting/ tracking/ features/ pipelines/
	@echo ""
	@echo "Linting complete."

format:
	@echo "Formatting code with black..."
	black models/ betting/ tracking/ features/ pipelines/ tests/
	@echo ""
	@echo "Sorting imports with ruff..."
	ruff check --fix --select I models/ betting/ tracking/ features/ pipelines/
	@echo ""
	@echo "Formatting complete."

typecheck:
	@echo "Running mypy type checker..."
	mypy models/ betting/ tracking/ --ignore-missing-imports

# =============================================================================
# Operations
# =============================================================================

run-daily:
	@echo "Running daily operations..."
	python scripts/daily_run.py --refresh --predict
	@echo "Daily run complete."

run-backtest:
	@echo "Running backtests..."
	python scripts/backtest_runner.py --sport ncaab --seasons 2020-2025
	@echo "Backtest complete."

run-reconcile:
	@echo "Running evening reconciliation..."
	python scripts/daily_run.py --reconcile
	@echo "Reconciliation complete."

# =============================================================================
# Claude Flow
# =============================================================================

cf-init:
	npx claude-flow@alpha init
	npx claude-flow@alpha memory init --reasoningbank

cf-status:
	npx claude-flow@alpha swarm status
	npx claude-flow@alpha agent list

cf-memory-list:
	@echo "=== Decisions ===" && npx claude-flow@alpha memory list --namespace betting/decisions
	@echo "=== Patterns ===" && npx claude-flow@alpha memory list --namespace betting/patterns
	@echo "=== Models ===" && npx claude-flow@alpha memory list --namespace betting/models
	@echo "=== Bugs ===" && npx claude-flow@alpha memory list --namespace betting/bugs

# =============================================================================
# Maintenance
# =============================================================================

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ 2>/dev/null || true
	@echo "Cleanup complete."

backup:
	@echo "Creating database backup..."
	mkdir -p backups
	cp data/betting.db backups/betting_$(shell date +%Y%m%d_%H%M%S).db
	@echo "Backup created in backups/"

backup-clean:
	@echo "Removing backups older than 30 days..."
	find backups/ -name "*.db" -mtime +30 -delete 2>/dev/null || true
	@echo "Old backups removed."

logs-clean:
	@echo "Archiving old logs..."
	find logs/ -name "*.log" -mtime +7 -exec gzip {} \; 2>/dev/null || true
	@echo "Logs archived."

# =============================================================================
# Jupyter
# =============================================================================

notebook:
	jupyter lab --notebook-dir=notebooks

# =============================================================================
# Documentation
# =============================================================================

docs:
	@echo "Documentation is in docs/ directory"
	@echo "Key files:"
	@echo "  - CLAUDE.md (AI context)"
	@echo "  - docs/DECISIONS.md (Architecture decisions)"
	@echo "  - docs/RUNBOOK.md (Operations)"
	@echo "  - docs/DATA_SOURCES.md (API documentation)"

# =============================================================================
# Quick Checks
# =============================================================================

check: lint typecheck test-fast
	@echo ""
	@echo "All checks passed!"

pre-commit:
	pre-commit run --all-files

# =============================================================================
# Database Queries (convenience)
# =============================================================================

db-shell:
	sqlite3 data/betting.db

db-bets:
	sqlite3 data/betting.db "SELECT * FROM bets ORDER BY placed_at DESC LIMIT 10;"

db-performance:
	sqlite3 data/betting.db "SELECT * FROM v_model_performance;"

db-daily:
	sqlite3 data/betting.db "SELECT * FROM v_daily_pnl ORDER BY date DESC LIMIT 7;"
