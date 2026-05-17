# 排课子系统 开发指南

> 本组组员唯一的开发入口文档。包含工作流 + 技术约定 + 项目规范。
> 数据契约（表结构、跨系统字段约定）见 [DATA_SCHEMA.md](./DATA_SCHEMA.md)。

---

## 目录

1. [快速开始](#1-快速开始)
2. [项目结构](#2-项目结构)
3. [统一响应格式 ApiResponse](#3-统一响应格式-apiresponse)
4. [异常与错误码约定](#4-异常与错误码约定)
5. [权限与认证](#5-权限与认证)
6. [后端：新增功能五步法](#6-后端新增功能五步法)
7. [Celery 异步任务约定](#7-celery-异步任务约定)
8. [前后端 API 契约](#8-前后端-api-契约)
9. [前端约定](#9-前端约定)
10. [测试约定](#10-测试约定)
11. [Git / 分支 / 提交约定](#11-git--分支--提交约定)
12. [PR 流程](#12-pr-流程)
13. [FAQ](#13-faq)

---

## 1. 快速开始

```bash
# 首次
cp .env.example .env
make build

# 日常
make up         # 启动
make down       # 停止（保留数据）
make reset      # 停止并清空数据库
make help       # 列出所有命令
```

代码改动会被 Uvicorn 的 `--reload` 自动热加载，无需重启容器。

**端口约定：**

| 端口 | 服务 |
|-----|------|
| 8002 | FastAPI 后端 |
| 5173 | Vue 前端（Vite dev server） |
| 3307 | MySQL（开发栈） |
| 6380 | Redis（开发栈） |
| 8003 / 3308 / 6381 | 测试栈（`docker-compose.test.yml`） |

**关键入口：**

- API Swagger UI：http://localhost:8002/docs
- OpenAPI JSON：http://localhost:8002/openapi.json
- 前端：http://localhost:5173

### 1.1 （可选）Linter

项目用 VSCode 扩展自带的 Ruff（Python lint + format）和 Prettier（前端 format）。

1. VSCode 打开项目，右下角弹"安装推荐扩展"点确定；或手动装：
   - `charliermarsh.ruff`
   - `esbenp.prettier-vscode`
   - `Vue.volar`
2. 保存代码（Ctrl+S）即自动整理 import、格式化、修小毛病
3. 要改linter规则去改 [`pyproject.toml`](../pyproject.toml) / [`frontend/.prettierrc`](../frontend/.prettierrc) 即可

---

## 2. 项目结构

```
schedule/
├── app/                      # FastAPI 后端
│   ├── algorithm/engine.py   # CP-SAT 算法入口（输入/输出 dataclass 已锁定）
│   ├── api/v1/               # 路由
│   ├── core/                 # config / database / exception_handlers / security
│   ├── models/               # SQLAlchemy 模型
│   ├── schemas/              # Pydantic DTO（含 ApiResponse / BizCode / BizException）
│   ├── services/             # 业务逻辑
│   └── tasks/                # Celery 任务（含算法链路）
├── frontend/                 # Vue 3 + Vite + Element Plus + Pinia
│   └── src/
│       ├── api/http.js       # axios 实例 + 拦截器（处理 ApiResponse）
│       ├── api/modules/*.js  # 按资源分模块的请求函数
│       ├── views/            # 一页一目录
│       ├── router/index.js
│       └── stores/           # Pinia store
├── tests/
│   ├── unit/                 # SQLite in-memory，无 Docker 依赖
│   ├── solver/               # 算法 golden case
│   ├── integration/          # 跑测试栈（docker-compose.test.yml）
│   └── e2e/                  # API 层端到端
├── docs/
│   ├── DEVELOPMENT_GUIDE.md  # 本文件
│   └── DATA_SCHEMA.md        # 数据契约
├── docker-compose.yml        # 开发栈
├── docker-compose.test.yml   # 测试栈（端口隔离）
├── Makefile
└── .env.example
```

---

## 3. 统一响应格式 ApiResponse

定义：[`app/schemas/response.py`](../app/schemas/response.py)

所有接口必须返回 `ApiResponse[T]`：

```json
// 成功
{ "code": 0, "msg": "success", "data": { ... } }

// 业务错误（HTTP 仍为 200）
{ "code": 2003, "msg": "无权限执行此操作", "data": null }

// 未捕获异常（HTTP 500，极少出现）
{ "code": 2098, "msg": "...", "data": null }
```

**规则：**

- 业务错误一律 **HTTP 200 + body.code≠0**，只有真未捕获异常才 5xx
- 路由层用 `ApiResponse.ok(data=...)` 包装成功返回
- 错误**不要**自己构造 ApiResponse —— 抛 `BizException`，由全局 handler 渲染（见 4.小节）

```python
from app.schemas.response import ApiResponse

@router.get("/classrooms", response_model=ApiResponse[list[ClassroomOut]])
async def list_classrooms(...):
    items = await classroom_service.list_all(db)
    return ApiResponse.ok(data=[ClassroomOut.model_validate(x) for x in items])
```

---

## 4. 异常与错误码约定

定义：[`app/schemas/response.py`](../app/schemas/response.py) · [`app/core/exception_handlers.py`](../app/core/exception_handlers.py)

**业务异常统一抛 `BizException`，不 `raise HTTPException(...)`。**

```python
from app.schemas.response import BizException, BizCode

if not classroom:
    raise BizException(BizCode.CLASSROOM_NOT_FOUND, "教室不存在")
```

全局 handler 会把它渲染成 `HTTP 200 + ApiResponse.fail(code, msg, data)`。

**错误码段位（排课组占用 2000–2099）：**

| 码 | 含义 |
|----|-----|
| 0 | 成功 |
| 2000 | 通用业务错误 |
| 2001 | 教室不存在 |
| 2002 | 排课任务未找到 |
| 2003 | 无权限执行此操作 |
| 2004 | 排课任务正在进行中，请勿重复触发 |
| 2005 | 上游服务数据拉取失败 |
| 2010 | 参数校验失败 |
| 2011 | 未授权 |
| 2012 | 禁止访问 |
| 2013 | 资源不存在 |
| 2098 | 服务内部错误 |
| 2099 | 排课算法无解（约束冲突） |

新增错误码：在 `BizCode` 类里加常量 + 在文件顶部 docstring 同步说明。

**handler 行为：**

| 异常类型 | 渲染结果 |
|---------|---------|
| `BizException` | HTTP 200 + `ApiResponse(code, msg, data)` |
| `RequestValidationError` | HTTP 200 + code=2010 + data=errors() |
| `HTTPException`（第三方/FastAPI 内部）| HTTP 200 + 按状态码映射业务码 |
| 未捕获 `Exception` | HTTP 500 + code=2098 |

---

## 5. 权限与认证

本服务不签发令牌，只消费网关透传的两个 header：

```
X-User-Id: <userId>
X-User-Role: ADMIN | TEACHER | STUDENT
```

权限依赖（位于 `app/api/dependencies.py`）：

| 依赖 | 允许角色 | 用法 |
|------|---------|------|
| `get_current_user` | 任意登录用户 | 查询接口 |
| `require_admin` | ADMIN | 触发排课、教室增删改 |
| `require_teacher_or_admin` | TEACHER + ADMIN | 教师写操作 |

```python
from app.api.dependencies import require_admin

@router.post("/classrooms")
async def create(..., _=Depends(require_admin)): ...
```

---

## 6. 后端：新增功能的步骤

```
1. app/schemas/<resource>.py     — Pydantic DTO（Create / Update / Out）
2. app/models/<resource>.py      — SQLAlchemy 模型（如需新表）
3. app/services/<resource>_service.py  — 业务逻辑
4. app/api/v1/<resource>.py      — 路由
5. app/main.py 中 include_router — 注册
```

**Model 新增后**：要在 `app/models/__init__.py`  中import 过，再重启 API 容器即可（`init_db()` 启动时调 `Base.metadata.create_all`）。需要改字段执行：`make reset && make build`。

**路由模板：**

```python
from fastapi import APIRouter, Depends
from app.core.database import get_db
from app.api.dependencies import require_admin
from app.schemas.response import ApiResponse
from app.schemas.foo import FooCreate, FooOut
from app.services import foo_service

router = APIRouter(prefix="/foo", tags=["Foo"])

@router.post("", response_model=ApiResponse[FooOut])
async def create_foo(data: FooCreate, db=Depends(get_db), _=Depends(require_admin)):
    obj = await foo_service.create(db, data)
    return ApiResponse.ok(data=FooOut.model_validate(obj))
```

---

## 7. Celery 异步任务约定

定义：[`app/tasks/celery_app.py`](../app/tasks/celery_app.py) · [`app/tasks/scheduler_tasks.py`](../app/tasks/scheduler_tasks.py)

**模式：接口立即返回 task_id，不阻塞 HTTP；任务内汇报进度。**

```python
# 接口层
task = run_auto_schedule.delay(semester)
return ApiResponse.ok(data={"task_id": task.id})

# 任务层
@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_auto_schedule(self, semester: str):
    self.update_state(state="PROGRESS", meta={"progress": 30, "message": "拉数据..."})
    # ...
    return {"result": ...}
```

**任务状态机：**`ScheduleTask` 表的 `status` 字段：

```
PENDING → RUNNING → SUCCESS
                  → FAILED
                  → PARTIAL   # 部分课无法排进，scheduled+unscheduled 都非空
```

**前端查进度**：`GET /api/v1/schedule/schedule-status/{task_id}` → 内部把 Celery state 映射到 `ScheduleStatus`。

---

## 8. 前后端 API 契约

**唯一事实是 FastAPI 自动生成的 OpenAPI**

| 我想看 | 去哪里看 |
|--------|---------|
| 当前所有端点 + 请求/响应 schema | http://localhost:8002/docs （Swagger UI） |
| 机器可读 schema | http://localhost:8002/openapi.json |
| Pydantic 源 schema | `app/schemas/*.py` |
| 错误码段位与含义 | `app/schemas/response.py` |
| 数据库表结构 / 跨子系统数据契约 | `docs/DATA_SCHEMA.md` |

**前端的 http 拦截器行为**（[`frontend/src/api/http.js`](../frontend/src/api/http.js)）：

- baseURL = `/api/v1`，超时 15s
- 请求拦截器：自动注入 `X-User-Id` / `X-User-Role`（从 Pinia auth store）
- 响应拦截器：
  - 收到 `{code, msg, data}` 且 `code === 0` → 直接返回 `data`（**自动 unwrap**）
  - 收到 `code !== 0` → Element Plus toast + 抛 `BizError`
  - 网络异常 → toast `网络异常: <status>`

**所以前端调用方写起来是这样：**

```js
import { listClassrooms } from '@/api/modules/classrooms'

// 这里拿到的是 data 本体，不是 ApiResponse 包裹
const rooms = await listClassrooms({ campus: '玉泉' })
```

**新增前端请求的步骤**：在 `frontend/src/api/modules/<resource>.js` 里追加，按已有模式（`classrooms.js`、`schedule.js`、`teacherPreferences.js`）写。

---

## 9. 前端约定

**技术栈**：Vue 3 + Vite + Pinia + Vue Router + Element Plus + Axios（无 TypeScript，无 codegen）。

**目录约定：**

```
frontend/src/
├── api/http.js                  # axios 实例 + 拦截器
├── api/modules/<resource>.js    # 按资源分文件，导出请求函数
├── views/<page>/Index.vue       # 一页一目录
├── router/index.js              # 路由表
├── stores/auth.js               # Pinia store；按需建其他 store
├── layouts/                     # 顶部/侧边导航等布局
└── main.js
```

**新增页面流程：**

```
1. frontend/src/views/<feature>/Index.vue   — 新建页面组件
2. frontend/src/router/index.js              — 注册路由
3. frontend/src/api/modules/<resource>.js    — 追加请求函数（如需）
4. （可选）frontend/src/stores/<feature>.js  — 需要跨组件共享状态时再建 Pinia store
```

**dev proxy**：`vite.config.js` 把 `/api` 转发到 `VITE_API_TARGET`（默认 `http://localhost:8002`）。所以前端代码里写 `/api/v1/...` 即可，开发/生产同源。

---

## 10. 测试约定

**四层 marker（`pytest.ini`）：**

| marker | 跑什么 | 依赖 | 命令 |
|--------|-------|------|------|
| `unit` | 服务/接口的单元测试（SQLite in-memory + ASGITransport） | 无 Docker | `make test-unit` |
| `solver` | 算法 golden case，直接调 `run_schedule()` | 无 Docker | `make test-solver` |
| `integration` | API + Celery + 真实 MySQL/Redis | 测试栈 | `make test-integration` |
| `e2e` | httpx 打测试栈 :8003 | 测试栈 | `make test-e2e` / `make test-smoke` |

**什么时候该写哪层？**

- 改了 service 的纯逻辑或路由的参数校验 → `unit`
- 改了 `run_schedule()` 或约束实现 → `solver`
- 改了 Celery 任务 / 跨服务调用 / DB 事务 → `integration`
- 改了前后端联动的完整业务流 → `e2e`

**fixture 在 `tests/conftest.py`**：`client`（ADMIN）、`student_client`（STUDENT）、`db_session`。需要别的角色就照样写一个 `teacher_client`。

**常用命令：**

```bash
make test            # unit + solver（快，无 Docker，提 PR 前过一遍）
make test-all        # 四层全跑（合主干前过）
make test-stack-up   # 单独起测试栈
make test-stack-down # 关测试栈
```

---

## 11. Git / 分支 / 提交约定

**分支命名**：`<type>/issue-<num>-<short-desc>`

```
feature/issue-3-classroom-crud
fix/issue-12-status-mapping
test/issue-16-preference-coverage
```

| type | 用途 |
|------|------|
| `feature` | 新功能 |
| `fix` | bug 修复 |
| `test` | 加/改测试 |
| `refactor` | 重构（不改行为） |
| `docs` | 仅文档 |
| `chore` | 杂项 |

**提交信息**：Conventional Commits（英文），关联 issue。

```
feat(classroom): add CRUD endpoints

Closes #3
```

---

## 12. PR 流程

1. 从 main 拉分支 → 提交 → push → 开 PR（标题 `<type>(#issue): ...`）
2. PR 描述至少包含：**改动内容** + **测试方法** + `Closes #N`
3. 本地 make test 通过
4. CI 自动跑 `unit + solver`；`integration + e2e` 在合主干前跑一次
5. 任意一名组员 approve 即可合，使用 **Squash and Merge**

---

## 13. FAQ

**Q: 代码改了 API 没更新？**
A: `make up` 已挂载本地目录，Uvicorn 自动 reload。不生效时 `docker compose restart schedule-api`。

**Q: Celery worker 不执行任务？**
A: `make logs-worker | grep ready` 看是否连上 Redis。

**Q: DB 表不存在？**
A: `docker compose restart schedule-api` —— 启动时 `init_db()` 自动建表。改了字段结构要 `make reset && make build`。

**Q: 测试报 `no event loop`？**
A: `pytest.ini` 已配 `asyncio_mode = auto`，并 `pytest-asyncio` 在 `requirements-test.txt`。重装依赖：`pip install -r requirements-test.txt`。

**Q: 前端页面空白 / `/api` 404？**
A: 确认后端已起：`docker compose ps`。前端 vite proxy `/api` → `schedule-api:8000`，后端没起则全部接口报错。

**Q: 上游基础信息服务不可用，本地怎么开发？**
A: `_fetch_upstream_data` 应有 fallback stub（B1 issue 实现）；当前阶段算法链路本身就在 scaffold，看 task_assignments 里 B1 卡。

---

> 如发现文档与代码不一致，**以代码为准**，并提 PR 修文档。
