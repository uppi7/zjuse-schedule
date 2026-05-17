# 自动排课子系统

软件工程教学服务系统 · 第二子系统

## 功能概览

根据教室、教师、课程数据，自动生成全学期课表，并支持人工微调。

> 完整接口与 schema 见 http://localhost:8002/docs。

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
make build       # 首次：构建镜像并启动所有容器
```

启动后访问：
- 前端页面：http://localhost:5173
- API 文档：http://localhost:8002/docs

```bash
make up          # 日常启动
make down        # 停止（保留数据）
make reset       # 停止并清除数据库
make help        # 查看所有命令
```

---

## 目录结构

```
zjuse-schedule/
├── app/                            # 后端（FastAPI）
│   ├── main.py                     # FastAPI 入口
│   ├── api/
│   │   ├── dependencies.py         # 权限依赖（require_admin 等）
│   │   └── v1/
│   │       ├── classrooms.py       # 教室 CRUD
│   │       ├── schedule.py         # 排课触发/状态/手动调整/查询
│   │       └── teacher_preferences.py  # 教师偏好 CRUD
│   ├── core/
│   │   ├── config.py               # 环境变量（Pydantic Settings）
│   │   ├── database.py             # SQLAlchemy 异步引擎
│   │   ├── security.py             # 网关 Header 解析
│   │   ├── exception_handlers.py   # 全局异常 → ApiResponse 渲染
│   │   └── external_clients.py     # 调用基础信息组（httpx）
│   ├── models/                     # 数据表定义
│   ├── schemas/                    # Pydantic DTO（含 ApiResponse / BizCode / BizException）
│   ├── services/                   # 业务逻辑
│   ├── algorithm/
│   │   └── engine.py               # 排课算法入口（I/O 已锁定；TODO: 替换 stub 为真实算法）
│   └── tasks/
│       ├── celery_app.py           # Celery 配置
│       └── scheduler_tasks.py      # 异步排课任务（含上游拉取/落库占位）
├── frontend/                       # 前端（Vue 3 + Vite + Element Plus + Pinia）
│   ├── Dockerfile                  # 生产镜像：node 构建 → nginx 服务
│   ├── nginx.conf                  # SPA 路由 + /api 反向代理
│   ├── package.json
│   ├── vite.config.js              # dev server :5173，/api 代理至后端
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── style.css
│       ├── api/
│       │   ├── http.js             # axios 实例 + 拦截器（处理 ApiResponse）
│       │   ├── modules/            # 按资源分模块的请求函数
│       │   └── index.js            # barrel 再导出
│       ├── router/index.js         # Vue Router 路由表
│       ├── stores/auth.js          # Pinia store（当前用户）
│       ├── layouts/                # 全局布局（侧边菜单 + 顶部 header）
│       └── views/                  # 一页一目录，每个目录下 Index.vue
│           ├── resources/          # 教室管理（占位）
│           ├── preferences/        # 教师偏好（占位）
│           ├── engine/             # 自动排课触发与进度（占位）
│           ├── adjust/             # 手动调课（占位）
│           └── timetable/          # 课表查询与打印（占位）
├── tests/
│   ├── conftest.py                 # 根 fixture（client / student_client，SQLite in-memory）
│   ├── factories.py                # 算法 dataclass 构造工厂
│   ├── unit/                       # 无 Docker 依赖；marker: unit
│   ├── solver/                     # 算法 golden case；marker: solver
│   ├── integration/                # 跑测试栈；marker: integration
│   └── e2e/                        # API 层端到端；marker: e2e / smoke
├── docs/
│   ├── DEVELOPMENT_GUIDE.md        # 开发指南（工作流 + 技术约定 + 项目规范）
│   └── DATA_SCHEMA.md              # 数据库表与跨系统 JSON 契约
├── .github/workflows/test.yml      # CI（unit+solver 必过、integration+e2e 合入前过）
├── CONTRIBUTING.md                 # 短桩，指向 docs/DEVELOPMENT_GUIDE.md
├── .env.example
├── Dockerfile
├── Makefile                        # 常用命令封装
├── docker-compose.yml              # 开发栈
├── docker-compose.test.yml         # 测试栈（端口隔离 8003/3308/6381）
├── pyproject.toml
├── pytest.ini
├── requirements.txt
└── requirements-test.txt
```

---

## 开发指引

**首先阅读 [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)**，包含完整的工作流、技术约定、项目规范。

其他参考文档：

| 文档 | 内容 |
|---|---|
| [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) | 工作流 + 技术约定 + ApiResponse / 异常 / 权限规范 |
| [docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md) | 数据库表结构与跨组 JSON 契约 |
| http://localhost:8002/docs | 完整接口列表与请求/响应 schema |
