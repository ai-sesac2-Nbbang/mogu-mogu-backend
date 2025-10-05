# Makefile
# 사용 예)
#   make start
#   make start PORT=9001 HOST=127.0.0.1
#   make format
#   make lint
#   make test
#   make typecheck
#   make fix
#   make clean

# ===== Config =====
POETRY      := poetry
RUN         := $(POETRY) run
UVICORN     := $(RUN) uvicorn
APP_MODULE  ?= app.main:app
HOST        ?= 0.0.0.0
PORT        ?= 8000
RELOAD      ?= --reload

# ===== Help =====
.PHONY: help
help:
	@echo "Targets:"
	@echo "  start       - FastAPI 개발 서버 실행 (uvicorn)"
	@echo "  migrate     - Alembic 마이그레이션 실행 (upgrade head)"
	@echo "  format      - ruff format -> ruff --fix -> mypy"
	@echo "  lint        - ruff check (읽기 전용) + mypy"
	@echo "  test        - pytest 실행"
	@echo "  typecheck   - mypy 타입 검사만"
	@echo "  fix         - ruff 자동 수정만"
	@echo "  clean       - 캐시/빌드 산출물 정리"

# ===== App =====
.PHONY: start
start:
	$(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT) $(RELOAD)

# ===== DB Migration =====
.PHONY: migrate
migrate:
	$(RUN) alembic upgrade head

# ===== Code Quality =====
.PHONY: format
format:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .
	$(RUN) mypy .

# 세분화된 타겟(원하면 개별 실행)
.PHONY: lint
lint:
	$(RUN) ruff check .
	$(RUN) mypy .

.PHONY: typecheck
typecheck:
	$(RUN) mypy .

.PHONY: fix
fix:
	$(RUN) ruff check --fix .

# ===== Tests =====
.PHONY: test
test:
	$(RUN) pytest -q

# ===== Clean =====
.PHONY: clean
clean:
	@echo "🧹 Cleaning up caches..."
	@rm -rf .mypy_cache .pytest_cache .ruff_cache dist build || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
