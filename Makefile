# ============================================================
# World News Intelligence Dashboard – Makefile
# ============================================================

.PHONY: install run-pipeline run-dashboard test lint format train-model setup cron-install

# ── Setup ────────────────────────────────────────────────────
install:
	pip install -r requirements.txt
	mkdir -p data/raw data/processed logs

# One-command setup (install deps + first pipeline run)
setup: install
	python -m scripts.run_pipeline --stage all
	@echo "✅ Setup complete. Run: make run-dashboard"

# ── Pipeline ─────────────────────────────────────────────────
run-pipeline:
	python -m scripts.run_pipeline --stage all

ingest-only:
	python -m scripts.run_pipeline --stage ingest

enrich-only:
	python -m scripts.run_pipeline --stage enrich

train-model:
	python -m scripts.run_pipeline --stage train

# ── Dashboard ────────────────────────────────────────────────
run-dashboard:
	streamlit run src/presentation/dashboard.py --server.port 8501

# ── Tests ────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

# ── Linting / Formatting ─────────────────────────────────────
lint:
	ruff check src/ tests/ scripts/

format:
	black src/ tests/ scripts/
	ruff check --fix src/ tests/ scripts/

# ── Cron job setup (Linux/macOS) ─────────────────────────────
# Installs a crontab entry to run the pipeline every 30 minutes
cron-install:
	@PROJ_DIR=$$(pwd); \
	CRON_CMD="*/30 * * * * cd $$PROJ_DIR && python -m scripts.run_pipeline --stage all >> $$PROJ_DIR/logs/cron.log 2>&1"; \
	(crontab -l 2>/dev/null | grep -v "run_pipeline"; echo "$$CRON_CMD") | crontab -; \
	echo "✅ Cron job installed: pipeline runs every 30 minutes"; \
	echo "   To verify: crontab -l"; \
	echo "   To remove: make cron-remove"

cron-remove:
	crontab -l 2>/dev/null | grep -v "run_pipeline" | crontab -
	@echo "✅ Cron job removed"

cron-status:
	@crontab -l 2>/dev/null | grep "run_pipeline" || echo "No pipeline cron job found"

# ── Cleanup ──────────────────────────────────────────────────
clean-db:
	rm -f data/processed/news.duckdb data/processed/classifier.pkl
	@echo "Database and model cleared"

clean-logs:
	rm -f logs/*.log

clean: clean-db clean-logs

# ── Help ─────────────────────────────────────────────────────
help:
	@echo "World News Intelligence Dashboard"
	@echo "=================================="
	@echo "  make install       – install Python dependencies"
	@echo "  make setup         – full first-time setup"
	@echo "  make run-pipeline  – fetch + enrich news now"
	@echo "  make run-dashboard – start Streamlit on port 8501"
	@echo "  make train-model   – retrain ML classifier"
	@echo "  make test          – run unit + integration tests"
	@echo "  make lint          – ruff linting"
	@echo "  make format        – black + ruff autofix"
	@echo "  make cron-install  – add 30-min cron job"
	@echo "  make cron-remove   – remove cron job"
	@echo "  make cron-status   – check cron job status"
	@echo "  make clean         – delete DB + logs"
