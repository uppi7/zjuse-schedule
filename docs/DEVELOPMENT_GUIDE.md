# 技术开发手册

> **工作流程** 见根目录 [CONTRIBUTING.md](../CONTRIBUTING.md)。  
> 本文档只记录技术层面的"怎么写代码"，不重复流程规范。

---

## 一、后端：添加新接口

按以下顺序创建文件，每步都有对应目录。

### Step 1 — Schema（DTO）

```python
# app/schemas/xxx.py
from pydantic import BaseModel, Field

class XxxCreate(BaseModel):
    name: str = Field(..., max_length=64)
    value: int = Field(..., gt=0)

class XxxOut(BaseModel):
    id: int
    name: str
    value: int
    model_config = {"from_attributes": True}
```

### Step 2 — Model（数据表，如需新表）

```python
# app/models/xxx.py
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Xxx(Base):
    __tablename__ = "xxx_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    value: Mapped[int]
```

新增 model 后，在 `app/models/__init__.py` 加一行 import，重启 API 容器即可（`init_db()` 会自动建表）：

```bash
docker compose restart schedule-api
```

### Step 3 — Service（业务逻辑）

```python
# app/services/xxx_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.xxx import Xxx
from app.schemas.response import BizCode

async def create_xxx(db: AsyncSession, data: XxxCreate) -> Xxx:
    obj = Xxx(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj
```

### Step 4 — Router（路由）

```python
# app/api/v1/xxx.py
from fastapi import APIRouter, Depends
from app.core.database import get_db
from app.api.dependencies import get_current_user, require_admin
from app.schemas.response import ApiResponse
from app.services import xxx_service

router = APIRouter(prefix="/xxx", tags=["XXX模块"])

@router.post("", response_model=ApiResponse[XxxOut], status_code=201)
async def create_xxx(data: XxxCreate, db=Depends(get_db), _=Depends(require_admin)):
    obj = await xxx_service.create_xxx(db, data)
    return ApiResponse.ok(data=XxxOut.model_validate(obj))
```

### Step 5 — 注册路由

```python
# app/main.py
from app.api.v1 import xxx
app.include_router(xxx.router, prefix=API_PREFIX)
```

---

## 二、后端：错误处理

**已知业务错误**（有对应错误码）：

```python
from fastapi import HTTPException, status
from app.schemas.response import BizCode

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": BizCode.CLASSROOM_NOT_FOUND, "msg": "教室不存在"}
)
```

**需要新增错误码**时，在 `app/schemas/response.py` 的 `BizCode` 类中添加。排课组号段：2000–2099。

---

## 三、后端：权限控制

| 依赖函数 | 允许角色 | 使用场景 |
|---|---|---|
| `get_current_user` | 所有登录用户 | 查询类接口 |
| `require_admin` | ADMIN 只 | 触发排课、创建/删除教室 |
| `require_teacher_or_admin` | TEACHER + ADMIN | 教师相关写操作 |

```python
# 查询接口（所有登录用户）
@router.get("", ...)
async def list_xxx(_user=Depends(get_current_user)): ...

# 写接口（仅管理员）
@router.post("", ...)
async def create_xxx(_admin=Depends(require_admin)): ...
```

---

## 四、后端：Celery 异步任务

触发耗时任务（排课算法）的标准模式：

```python
# 接口层：立即返回 task_id，不阻塞
celery_task = some_task.delay(arg1, arg2)
return ApiResponse.ok(data={"task_id": celery_task.id})

# 任务层：汇报进度
@celery_app.task(bind=True)
def some_task(self, arg1, arg2):
    self.update_state(state="PROGRESS", meta={"progress": 30, "message": "处理中..."})
    # ... 执行逻辑 ...
    return {"result": "done"}
```

查询进度：`celery.result.AsyncResult(task_id, app=celery_app).state`

---

## 五、后端：调用上游服务（基础信息组）

```python
from app.core.external_clients import get_info_client

client = get_info_client()
teachers = await client.get_all_teachers()   # 返回 list[dict]
courses  = await client.get_all_courses()
```

上游不可用时会抛出 `httpx.HTTPError`，在 Celery 任务中已有 fallback stub，开发阶段无需关心。

---

## 六、测试：编写测试用例

测试使用 SQLite 内存库，直接 `pytest tests/ -v` 即可，无需启动 MySQL。

### 基础结构

```python
# tests/test_xxx.py
import pytest
from httpx import AsyncClient

async def test_create_xxx(client: AsyncClient):          # ADMIN 角色
    resp = await client.post("/api/v1/xxx", json={...})
    assert resp.status_code == 201
    assert resp.json()["code"] == 0

async def test_create_xxx_forbidden(student_client: AsyncClient):  # STUDENT 角色
    resp = await student_client.post("/api/v1/xxx", json={...})
    assert resp.status_code == 403
```

### 可用 Fixture（定义在 `tests/conftest.py`）

| Fixture | 说明 |
|---|---|
| `client` | ADMIN 角色的 HTTP 客户端 |
| `student_client` | STUDENT 角色的 HTTP 客户端 |
| `db_session` | 数据库 Session（每个测试后回滚） |

### 需要其他角色时

```python
# tests/conftest.py 中添加
@pytest.fixture
async def teacher_client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-User-Id": "teacher-001", "X-User-Role": "TEACHER"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
```

---

## 七、前端开发

前端技术栈：**Vue 3 + Vite**，代码位于 `frontend/`。

| 模式 | 说明 | 访问地址 |
|---|---|---|
| 开发（docker compose） | Vite dev server，支持热更新 | http://localhost:5173 |
| 生产（frontend/Dockerfile） | nginx 服务编译产物，用于最终镜像提交 | :80 |

日常开发直接 `docker compose up --build`，访问 http://localhost:5173 即可。

### 添加新页面

```
1. frontend/src/views/NewPage.vue   — 新建页面组件
2. frontend/src/router/index.js     — 注册路由
3. frontend/src/App.vue             — 导航栏加链接（可选）
4. frontend/src/api/index.js        — 追加接口调用方法（如需）
```

**页面模板：**

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const data = ref([])
async function load() {
  const res = await api.someMethod()
  data.value = res.data
}
onMounted(load)
</script>

<template>
  <div class="page">
    <h2>页面标题</h2>
    <!-- 内容 -->
  </div>
</template>
```

**注册路由（`router/index.js`）：**

```javascript
{ path: '/new-page', component: () => import('../views/NewPage.vue') }
```

### 添加新接口调用

在 `frontend/src/api/index.js` 的 `api` 对象末尾追加：

```javascript
export const api = {
  // ... 已有方法 ...
  getClassrooms: () => request('GET', '/api/v1/classrooms'),
  createClassroom: (body) => request('POST', '/api/v1/classrooms', body),
}
```

`request` 函数已自动携带认证 Header，无需在页面组件里重复处理。

### 修改后热更新

前端文件修改后 Vite 自动热更新，**无需重启容器**，刷新浏览器即可看到效果。

### 生产镜像构建

`frontend/Dockerfile` 使用多阶段构建：node 编译 → nginx 服务。

```bash
# 本地验证生产镜像是否正常
docker build -t schedule-frontend:local ./frontend
docker run -p 8080:80 schedule-frontend:local
# 访问 http://localhost:8080（需后端同时运行）
```

nginx 通过 `frontend/nginx.conf` 配置：`/api/` 请求代理至 `schedule-api:8000`，其余路径走 SPA fallback。

---

## 八、数据库建表

项目使用 `Base.metadata.create_all` 在 API 启动时自动建表，无需手动迁移命令。

- 新增 Model → 在 `app/models/__init__.py` 加 import → 重启 API 容器，新表自动创建
- 已有表不会被删除或修改（`create_all` 只创建不存在的表）
- 如果需要修改已有字段，直接 `docker compose down -v` 清空数据后重建

---

## 八、常见问题

**Q: 修改代码后 Docker 内的 API 没有更新？**  
A: `docker compose up` 已挂载本地目录，Uvicorn `--reload` 模式会自动重启。如果不生效，`docker compose restart schedule-api`。

**Q: Celery Worker 没有执行任务？**  
A: 检查 Redis 连接：`docker compose logs schedule-worker | grep "ready"`。

**Q: 数据库表不存在？**  
A: `docker compose restart schedule-api`（启动时 `init_db()` 自动建表）。如果表结构有改动需要重置，用 `docker compose down -v && docker compose up --build`。

**Q: 测试报 `no event loop`？**  
A: 确认 `pytest.ini` 中有 `asyncio_mode = auto`，且 `pytest-asyncio` 已安装。

**Q: 前端页面空白或 `/api` 请求 404？**  
A: 确认后端容器已启动（`docker compose ps`）。Vite proxy 把 `/api` 转发到 `schedule-api:8000`，后端不起则所有接口报错。

**Q: 前端修改后没有更新？**  
A: Vite 热更新有时需要手动刷新浏览器。如果还是不生效，检查 `docker compose logs schedule-frontend` 是否有编译错误。
