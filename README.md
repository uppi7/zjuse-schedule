# 自动排课子系统（Automatic Course Arrangement）


## 目录

1. [系统概述](#1-系统概述)
2. [技术栈](#2-技术栈)
3. [目录结构](#3-目录结构)
4. [快速启动](#4-快速启动)
5. [开发指南](#5-开发指南)
6. [API 接口说明](#6-api-接口说明)
7. [跨组协商待办事项](#7-跨组协商待办事项-重要)
8. [角色分工建议](#8-角色分工建议)

---

## 1. 系统概述

本子系统负责根据课程、教师、教室数据，**自动生成排课结果**，并支持教务管理员手动调课。

### 核心功能

| 功能 | 描述 |
|---|---|
| 自动排课 | 异步触发排课算法，生成全学期课表 |
| 排课状态查询 | 实时轮询排课进度（0-100%） |
| 手动调课 | 对排课结果进行人工微调 |
| 课表查询 | 按学期/教师/课程查询课表 |
| 教室管理 | 教室 CRUD，维护教室容量和类型信息 |

### 架构说明

```
前端 → [API Gateway] → FastAPI (schedule-api:8002)
                            │
                            ├── 同步请求（教室 CRUD、课表查询）→ MySQL
                            │
                            └── 触发排课 → Celery Worker ─→ 排课算法
                                              │
                                              ├── 结果写入 MySQL
                                              └── 进度存储 Redis
```

排课采用**异步解耦**架构：
- 触发接口立即返回 `task_id`（不阻塞）
- 前端通过 `task_id` 轮询进度
- Worker 进程独立执行 CPU 密集型算法

---

## 2. 技术栈

| 层次 | 技术 | 版本 |
|---|---|---|
| Web 框架 | FastAPI | 0.111 |
| ASGI 服务器 | Uvicorn | 0.29 |
| 异步任务 | Celery | 5.4 |
| 消息队列/缓存 | Redis | 7 |
| ORM | SQLAlchemy (asyncio) | 2.0 |
| 数据库 | MySQL | 8.0 |
| 数据校验 | Pydantic v2 | 2.7 |
| 跨服务 HTTP | httpx | 0.27 |
| 容器化 | Docker / Docker Compose | - |

---

## 3. 目录结构

```
automatic-course-arrangement/
├── app/
│   ├── main.py                    # FastAPI 入口，路由注册，生命周期管理
│   ├── api/
│   │   ├── dependencies.py        # 依赖注入（当前用户、权限校验）
│   │   └── v1/
│   │       ├── classrooms.py      # 教室 CRUD 接口
│   │       └── schedule.py        # 排课触发、进度查询、调课接口
│   ├── core/
│   │   ├── config.py              # 环境变量配置（Pydantic Settings）
│   │   ├── database.py            # SQLAlchemy 异步引擎与 Session
│   │   ├── security.py            # 解析网关透传 Header
│   │   └── external_clients.py    # httpx 跨服务调用封装
│   ├── models/
│   │   ├── classroom.py           # 教室数据表
│   │   └── schedule.py            # 排课任务、课表条目数据表
│   ├── schemas/
│   │   ├── response.py            # 统一响应格式 {code, msg, data}
│   │   ├── classroom.py           # 教室 DTO
│   │   └── schedule.py            # 排课相关 DTO
│   ├── services/
│   │   ├── classroom_service.py   # 教室业务逻辑
│   │   └── schedule_service.py    # 排课业务逻辑
│   ├── algorithm/
│   │   └── engine.py              # 排课算法引擎入口（算法组在此实现）
│   └── tasks/
│       ├── celery_app.py          # Celery 实例初始化
│       └── scheduler_tasks.py     # 排课 Celery Task 定义
├── .env.example                   # 环境变量模板
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## 4. 快速启动

### 前提条件

- Docker 已安装并运行
- `git clone` 本仓库后 `cd automatic-course-arrangement`

### 步骤

```bash
# 1. 复制环境变量模板
cp .env.example .env

# 2. 一键启动所有服务（MySQL + Redis + API + Worker）
docker compose up --build

# 3. 访问交互式 API 文档
# 浏览器打开：http://localhost:8002/docs

# 4. 健康检查
curl http://localhost:8002/health
```

### 停止服务

```bash
docker compose down          # 停止但保留数据
docker compose down -v       # 停止并清除 volume 数据
```

---

## 5. 开发指南

### 本地开发（不用 Docker）

```bash
# 创建虚拟环境
python -m venv venv && source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（修改为本地服务地址）
cp .env.example .env
# 编辑 .env，将 MYSQL_HOST=localhost, REDIS_HOST=localhost

# 启动 FastAPI
uvicorn app.main:app --reload --port 8002

# 另开终端，启动 Celery Worker
celery -A app.tasks.celery_app.celery_app worker --loglevel=info
```

### 数据库迁移（Alembic）

```bash
# 初始化（首次）
alembic init alembic

# 生成迁移脚本
alembic revision --autogenerate -m "init tables"

# 执行迁移
alembic upgrade head
```

### 运行测试

```bash
pytest tests/ -v
```

---

## 6. API 接口说明

所有接口统一返回格式：

```json
{"code": 0, "msg": "success", "data": {...}}
```

`code=0` 表示成功，非零为错误（错误码见 `app/schemas/response.py`）。

### 6.1 触发自动排课

```
POST /api/v1/schedule/auto-schedule
权限：ADMIN

请求体：
{"semester": "2024-2025-1"}

响应：
{"code": 0, "msg": "Schedule task submitted", "data": {"task_id": "xxx", "semester": "2024-2025-1"}}
```

### 6.2 查询排课进度

```
GET /api/v1/schedule/schedule-status/{task_id}
权限：全部登录用户

响应：
{
  "code": 0, "msg": "success",
  "data": {
    "task_id": "xxx",
    "status": "RUNNING",    // PENDING | RUNNING | SUCCESS | FAILED
    "progress": 70,         // 0-100
    "message": "算法运行中...",
    "result_summary": null  // SUCCESS 时返回摘要
  }
}
```

### 6.3 手动调课

```
POST /api/v1/schedule/manual-adjust
权限：ADMIN

请求体：
{
  "entry_id": 42,
  "new_classroom_id": 3,
  "new_day_of_week": 2,
  "new_slot_start": 3,
  "new_slot_end": 4
}
```

### 6.4 查询课表

```
GET /api/v1/schedule/entries?semester=2024-2025-1&teacher_id=T001
权限：全部登录用户
```

### 6.5 教室管理

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/classrooms` | 全部 | 教室列表 |
| POST | `/api/v1/classrooms` | ADMIN | 新增教室 |
| GET | `/api/v1/classrooms/{id}` | 全部 | 单个教室 |
| PATCH | `/api/v1/classrooms/{id}` | ADMIN | 更新教室 |
| DELETE | `/api/v1/classrooms/{id}` | ADMIN | 删除教室 |

完整文档见启动后的 Swagger UI：http://localhost:8002/docs

---

## 7. 跨组协商待办事项（重要）

> 以下事项需在开发开始前与相关小组确认，**影响核心接口联调**。

### 🔴 与第一组（基础信息组）协商

| 编号 | 事项 | 当前假设值 | 配置位置 |
|---|---|---|---|
| P1-1 | 教师 API 的内网服务名、端口、URL 路径 | `http://info-service:8000/api/v1/teachers` | `.env` → `INFO_SERVICE_*` |
| P1-2 | 课程 API 的内网服务名、端口、URL 路径 | `http://info-service:8000/api/v1/courses` | `.env` → `INFO_SERVICE_*` |
| P1-3 | 教师 API 返回的 JSON 字段结构 | `[{"teacher_id":"T001","name":"张三"}]` | `external_clients.py` |
| P1-4 | 课程 API 返回的 JSON 字段结构 | `[{"course_id":"C001","student_count":50}]` | `external_clients.py` |
| P1-5 | 网关透传用户 ID 的 Header 字段名 | `X-User-Id` | `.env` → `AUTH_HEADER_USER_ID` |
| P1-6 | 网关透传用户角色的 Header 字段名 | `X-User-Role` | `.env` → `AUTH_HEADER_USER_ROLE` |
| P1-7 | "教务管理员"角色的 Role Code | `ADMIN` | `.env` → `ROLE_ADMIN` |

### 🔴 与第三组（智能选课组）协商

| 编号 | 事项 | 说明 |
|---|---|---|
| P3-1 | 排课结果的交付方式 | 方案A：MQ 事件广播；方案B：提供批量拉取 API（框架已实现 `GET /api/v1/schedule/entries`） |
| P3-2 | 若选方案A，确认 MQ 类型和事件格式 | Redis Pub/Sub 还是 Kafka？事件字段定义？ |

### 🟡 与大组协商

| 编号 | 事项 | 当前假设值 | 配置位置 |
|---|---|---|---|
| PM-1 | 排课组全局业务错误码号段 | `2000-2099` | `schemas/response.py` → `BizCode` |
| PM-2 | 排课组占用 Redis DB 编号 | DB 2（broker）、DB 3（result） | `.env` → `CELERY_*_DB` |
| PM-3 | 全局集成时 MySQL/Redis 内网服务别名 | `mysql` / `redis` | `.env` → `MYSQL_HOST` / `REDIS_HOST` |
| PM-4 | 本子系统的 Docker 内网端口 | API 对外 8002 | `docker-compose.yml` |

---

## 8. 角色分工建议

| 角色 | 主要工作文件 |
|---|---|
| **后端（API）** | `app/api/v1/`、`app/services/`、`app/schemas/`、`app/core/external_clients.py` |
| **后端（算法）** | `app/algorithm/engine.py`、`app/tasks/scheduler_tasks.py` |
| **前端** | 对接 `GET /api/v1/schedule/schedule-status/{task_id}` 实现进度轮询；对接 `GET /api/v1/schedule/entries` 展示课表 |
| **测试** | `tests/` 目录（见下方测试文档） |
| **运维** | `Dockerfile`、`docker-compose.yml`、`.env` |
