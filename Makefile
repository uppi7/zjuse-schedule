.PHONY: help up build down reset logs logs-api logs-worker test smoke db health push

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

test: ## 运行单元测试（无需启动 Docker）
	pytest tests/ -v

smoke: ## 运行集成冒烟测试（需先 make up）
	bash tests/smoke_test.sh

# ── 数据库 ────────────────────────────────────────────────────────────────

db: ## 进入 MySQL 交互命令行
	docker compose exec mysql mysql -uroot -prootpassword course_arrange

# ── 验证 ──────────────────────────────────────────────────────────────────

health: ## 检查 API 健康状态
	@curl -s http://localhost:8002/health | python3 -m json.tool

# ── 镜像发布 ──────────────────────────────────────────────────────────────

push: ## 构建并推送镜像到 ghcr.io（用法：make push VERSION=v0.1.0）
	docker build -t schedule-api:$(VERSION) .
	docker tag schedule-api:$(VERSION) ghcr.io/uppi7/schedule-api:$(VERSION)
	docker push ghcr.io/uppi7/schedule-api:$(VERSION)
	docker build -t schedule-frontend:$(VERSION) ./frontend
	docker tag schedule-frontend:$(VERSION) ghcr.io/uppi7/schedule-frontend:$(VERSION)
	docker push ghcr.io/uppi7/schedule-frontend:$(VERSION)
	@echo "✓ 已推送：schedule-api:$(VERSION)  schedule-frontend:$(VERSION)"
