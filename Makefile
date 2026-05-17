.PHONY: help up build down reset logs logs-api logs-worker test test-unit test-integration test-solver test-e2e test-smoke test-all test-stack-up test-stack-down db health push

VERSION ?= latest

help: ## 显示所有可用命令
	@echo ""
	@echo "用法：make <命令>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── 容器管理 ──────────────────────────────────────────────────────────────

up: ## 启动所有容器（日常开发，不重新构建）
	docker compose up -d

build: ## 重新构建镜像并启动（首次运行或修改了 requirements.txt / Dockerfile 后）
	docker compose up --build -d

down: ## 停止容器（保留数据库数据）
	docker compose down

reset: ## 停止容器并清除所有数据（慎用，数据不可恢复）
	docker compose down -v

# ── 日志 ──────────────────────────────────────────────────────────────────

logs: ## 查看所有容器的实时日志
	docker compose logs -f

logs-api: ## 查看 API 服务日志
	docker compose logs -f schedule-api

logs-worker: ## 查看 Celery Worker 日志
	docker compose logs -f schedule-worker

# ── 测试 ──────────────────────────────────────────────────────────────────

test: ## 本地快速测试：unit + solver（无需 Docker）
	pytest -m "unit or solver" -v

test-unit: ## 只跑 unit 层（SQLite in-memory，无 Docker 依赖）
	pytest -m unit -v

test-solver: ## 只跑 solver 层（纯 Python，无 Docker 依赖）
	pytest -m solver -v

test-integration: test-stack-up ## 集成层（依赖 docker-compose.test.yml）
	pytest -m integration -v ; rc=$$? ; $(MAKE) test-stack-down ; exit $$rc

test-e2e: test-stack-up ## E2E 层
	pytest -m e2e -v ; rc=$$? ; $(MAKE) test-stack-down ; exit $$rc

test-smoke: test-stack-up ## E2E层的smoke-test子集
	pytest -m smoke -v ; rc=$$? ; $(MAKE) test-stack-down ; exit $$rc

test-all: test-stack-up ## 跑全四层（unit + solver + integration + e2e）
	pytest -v ; rc=$$? ; $(MAKE) test-stack-down ; exit $$rc

test-stack-up: ## 启动测试栈（隔离的 MySQL/Redis/API/Worker）
	docker compose -f docker-compose.test.yml up -d --wait

test-stack-down: ## 停止测试栈并清除数据卷
	docker compose -f docker-compose.test.yml down -v

# ── 数据库 ────────────────────────────────────────────────────────────────

db: ## 进入 MySQL 交互命令行
	docker compose exec mysql mysql -uroot -prootpassword course_arrange

# ── 镜像发布 ──────────────────────────────────────────────────────────────

push: ## 构建并推送镜像到 ghcr.io（用法：make push VERSION=v0.1.0）
	docker build -t schedule-api:$(VERSION) .
	docker tag schedule-api:$(VERSION) ghcr.io/uppi7/schedule-api:$(VERSION)
	docker push ghcr.io/uppi7/schedule-api:$(VERSION)
	docker build -t schedule-frontend:$(VERSION) ./frontend
	docker tag schedule-frontend:$(VERSION) ghcr.io/uppi7/schedule-frontend:$(VERSION)
	docker push ghcr.io/uppi7/schedule-frontend:$(VERSION)
	@echo "✓ 已推送：schedule-api:$(VERSION)  schedule-frontend:$(VERSION)"
