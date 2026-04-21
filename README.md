# 自动排课子系统

大型软件工程教学服务系统 · 第二子系统

---

## 功能概览

根据教室、教师、课程数据，自动生成全学期课表，并支持人工微调。

| 接口 | 说明 |
|---|---|
| `POST /api/v1/schedule/auto-schedule` | 触发排课（异步，立即返回 task_id） |
| `GET /api/v1/schedule/schedule-status/{task_id}` | 查询排课进度 0–100% |
| `POST /api/v1/schedule/manual-adjust` | 手动调课 |
| `GET /api/v1/schedule/entries` | 查询课表（按学期/教师/课程筛选） |
| `CRUD /api/v1/classrooms` | 教室管理 |

## 架构

```
前端 ──→ [API Gateway] ──→ FastAPI (8002)
                               │
                ┌──────────────┴──────────────┐
                ↓                             ↓
        同步（教室/课表查询）         触发排课 → Celery Worker
                ↓                             ↓
              MySQL                    排课算法（CPU 密集）
                                              ↓
                                    结果写 MySQL，进度存 Redis
```

**技术栈：** FastAPI · Celery · Redis · MySQL · SQLAlchemy asyncio · Pydantic v2 · httpx · Vue 3 · Vite · Docker

---

## 快速启动

```bash
git clone git@github.com:uppi7/zjuse-schedule.git
cd zjuse-schedule
cp .env.example .env
docker compose up --build
```

启动后访问：
- 前端页面：http://localhost:5173
- API 文档：http://localhost:8002/docs
- 健康检查：http://localhost:8002/health

```bash
docker compose down      # 停止（保留数据）
docker compose down -v   # 停止并清除数据
```

---

## 目录结构

```
zjuse-schedule/
├── app/                            # 后端（FastAPI）
│   ├── main.py                     # FastAPI 入口
│   ├── api/v1/
│   │   ├── classrooms.py           # 教室 CRUD
│   │   └── schedule.py             # 排课接口
│   ├── core/
│   │   ├── config.py               # 环境变量（Pydantic Settings）
│   │   ├── database.py             # SQLAlchemy 异步引擎
│   │   ├── security.py             # 网关 Header 解析
│   │   └── external_clients.py     # 调用基础信息组（httpx）
│   ├── models/                     # 数据表定义
│   ├── schemas/                    # Pydantic DTO
│   ├── services/                   # 业务逻辑
│   ├── algorithm/
│   │   └── engine.py               # 排课算法入口（算法组实现此文件）
│   └── tasks/
│       ├── celery_app.py           # Celery 配置
│       └── scheduler_tasks.py      # 异步排课任务
├── frontend/                       # 前端（Vue 3 + Vite）
│   ├── Dockerfile                  # 生产镜像：node 构建 → nginx 服务
│   ├── nginx.conf                  # SPA 路由 + /api 反向代理
│   ├── package.json
│   ├── vite.config.js              # dev server :5173，/api 代理至后端
│   ├── index.html
│   └── src/
│       ├── api/index.js            # 统一 fetch 封装（含认证 Header）
│       ├── router/index.js         # Vue Router 路由表
│       ├── App.vue                 # 顶部导航
│       └── views/
│           ├── ScheduleTrigger.vue # 触发排课 + 进度条（Issue #9）
│           └── ScheduleEntries.vue # 课表查询表格（Issue #10）
├── tests/
│   ├── conftest.py                 # pytest fixtures（SQLite 内存库）
│   ├── test_classrooms.py
│   └── smoke_test.sh               # 集成冒烟测试
├── docs/
│   ├── DEVELOPMENT_GUIDE.md        # 技术开发手册
│   ├── DATA_SCHEMA.md              # 数据库表与跨系统 JSON 契约
│   ├── ISSUE_PLAN.md               # GitHub Issue 规划
│   └── NEGOTIATION_CHECKLIST.md    # 跨组约定记录
├── CONTRIBUTING.md                 # 开发工作流（必读）
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

---

## 开发

**首先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)**，包含完整工作流：领取 Issue → 开发 → 测试 → PR → Code Review → 合并。

```bash
# 运行单元测试（无需启动 Docker）
pytest tests/ -v

# 集成冒烟测试（需 docker compose up 后执行）
bash tests/smoke_test.sh
```

其他参考文档：

| 文档 | 内容 |
|---|---|
| [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) | 如何添加后端接口、前端页面、编写测试 |
| [docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md) | 数据库表结构与跨组 JSON 格式 |
| [docs/ISSUE_PLAN.md](docs/ISSUE_PLAN.md) | 全部待办 Issue 及认领建议 |
