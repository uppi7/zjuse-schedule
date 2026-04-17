# 开发指南

面向**后端开发、前端开发、测试人员**的详细说明。

---

## 一、后端开发指南

### 1.1 添加新接口的标准流程

1. **在 `app/schemas/` 中定义请求/响应 DTO**

```python
# app/schemas/xxx.py
from pydantic import BaseModel

class XxxCreate(BaseModel):
    field1: str
    field2: int

class XxxOut(BaseModel):
    id: int
    field1: str
    model_config = {"from_attributes": True}
```

2. **在 `app/models/` 中定义数据表（如需新表）**

```python
# app/models/xxx.py
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Xxx(Base):
    __tablename__ = "xxx_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    field1: Mapped[str]
```

3. **在 `app/services/` 中编写业务逻辑**

```python
# app/services/xxx_service.py
async def create_xxx(db: AsyncSession, data: XxxCreate) -> Xxx:
    obj = Xxx(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj
```

4. **在 `app/api/v1/` 中编写路由**

```python
# app/api/v1/xxx.py
from fastapi import APIRouter, Depends
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/xxx", tags=["XXX模块"])

@router.post("", response_model=ApiResponse[XxxOut])
async def create_xxx(data: XxxCreate, db=Depends(get_db)):
    obj = await xxx_service.create_xxx(db, data)
    return ApiResponse.ok(data=XxxOut.model_validate(obj))
```

5. **在 `app/main.py` 中注册路由**

```python
from app.api.v1 import xxx
app.include_router(xxx.router, prefix=API_PREFIX)
```

---

### 1.2 修改排课算法（算法组）

打开 [app/algorithm/engine.py](../app/algorithm/engine.py)，找到 `run_schedule()` 函数并替换其中的 stub 实现。

**接口约定（不得更改）：**

```python
def run_schedule(
    courses: list[CourseInput],
    classrooms: list[ClassroomInput],
    teachers: list[TeacherAvailability],
) -> tuple[list[ScheduleResult], list[str]]:
    # 返回：(成功排课列表, 未能排课的 course_id 列表)
    ...
```

算法运行在 Celery Worker 进程中，为纯同步 Python 代码，**不能使用 `async`**。

**在任务中汇报进度（可选）：**

在 `app/tasks/scheduler_tasks.py` 的 `run_auto_schedule` 任务里，通过以下方式更新进度：

```python
self.update_state(state="PROGRESS", meta={"progress": 50, "message": "算法运行到一半了"})
```

---

### 1.3 调用上游微服务

统一通过 `app/core/external_clients.py` 中的 `InfoServiceClient`：

```python
from app.core.external_clients import get_info_client

client = get_info_client()
teachers = await client.get_all_teachers()
courses = await client.get_all_courses()
```

> ⚠️ 上游 API URL 由 `.env` 中的 `INFO_SERVICE_*` 变量控制，
> 正式联调前需与第一组确认后更新。

---

### 1.4 统一错误处理

**不要直接返回 HTTP 500**，使用以下方式：

```python
from fastapi import HTTPException, status
from app.schemas.response import BizCode

# 已知业务错误
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": BizCode.CLASSROOM_NOT_FOUND, "msg": "教室不存在"}
)

# 新增错误码：在 app/schemas/response.py 的 BizCode 类中添加
```

---

## 二、前端开发指南

### 2.1 认证 Header

每个请求需携带网关透传的认证 Header：

```http
X-User-Id: <用户ID>
X-User-Role: ADMIN   # 或 TEACHER / STUDENT
```

> ⚠️ Header 字段名待与第一组确认，正式确认后更新此处。

### 2.2 排课功能的前端交互流程

```
1. 管理员点击"触发排课"
   → POST /api/v1/schedule/auto-schedule
   ← {"data": {"task_id": "abc123", "semester": "..."}}

2. 保存 task_id，开始轮询（每 3 秒一次）
   → GET /api/v1/schedule/schedule-status/abc123
   ← {"data": {"status": "RUNNING", "progress": 45, "message": "算法运行中..."}}

3. 显示进度条（progress: 0→100）

4. 当 status === "SUCCESS" 时停止轮询
   ← {"data": {"status": "SUCCESS", "progress": 100, "result_summary": {...}}}

5. 跳转到课表展示页面
   → GET /api/v1/schedule/entries?semester=2024-2025-1
```

### 2.3 响应格式

所有接口统一格式：

```typescript
interface ApiResponse<T> {
  code: number;    // 0=成功，非零=错误
  msg: string;
  data: T | null;
}
```

### 2.4 本地联调配置

前端 dev server 代理配置（以 Vite 为例）：

```javascript
// vite.config.js
server: {
  proxy: {
    '/api': 'http://localhost:8002'
  }
}
```

---

## 三、测试人员指南

### 3.1 测试环境搭建

```bash
# 启动后端（包含测试用 MySQL 和 Redis）
docker compose up --build

# 等待 http://localhost:8002/health 返回 {"status": "ok"}
```

### 3.2 使用 Swagger UI 测试

访问 http://localhost:8002/docs

每个请求需先在 Swagger 页面顶部点击 "Authorize" 并填写：

```
X-User-Id: testuser001
X-User-Role: ADMIN
```

### 3.3 关键测试场景

#### 场景 1：完整排课流程

```bash
# Step 1: 触发排课
curl -X POST http://localhost:8002/api/v1/schedule/auto-schedule \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin001" \
  -H "X-User-Role: ADMIN" \
  -d '{"semester": "2024-2025-1"}'
# 记录返回的 task_id

# Step 2: 查询进度（每隔几秒执行）
curl http://localhost:8002/api/v1/schedule/schedule-status/<task_id> \
  -H "X-User-Id: admin001" \
  -H "X-User-Role: ADMIN"

# Step 3: 查询结果
curl "http://localhost:8002/api/v1/schedule/entries?semester=2024-2025-1" \
  -H "X-User-Id: admin001" \
  -H "X-User-Role: ADMIN"
```

#### 场景 2：权限拦截测试

```bash
# 学生角色触发排课，应返回 403
curl -X POST http://localhost:8002/api/v1/schedule/auto-schedule \
  -H "Content-Type: application/json" \
  -H "X-User-Id: student001" \
  -H "X-User-Role: STUDENT" \
  -d '{"semester": "2024-2025-1"}'
```

#### 场景 3：教室 CRUD

```bash
# 创建教室
curl -X POST http://localhost:8002/api/v1/classrooms \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin001" \
  -H "X-User-Role: ADMIN" \
  -d '{"code":"A101","name":"A座101","building":"A座","capacity":120,"room_type":"LECTURE"}'

# 查询教室列表
curl http://localhost:8002/api/v1/classrooms \
  -H "X-User-Id: admin001" -H "X-User-Role: ADMIN"
```

### 3.4 编写自动化测试

测试文件放在 `tests/` 目录，使用 `pytest-asyncio`：

```python
# tests/test_classrooms.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_create_classroom():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/classrooms",
            json={"code": "B202", "name": "B座202", "building": "B座",
                  "capacity": 80, "room_type": "LECTURE"},
            headers={"X-User-Id": "admin", "X-User-Role": "ADMIN"},
        )
    assert resp.status_code == 201
    assert resp.json()["code"] == 0
```

运行测试：

```bash
pytest tests/ -v
```

---

## 四、常见问题

**Q: Celery Worker 看不到任务怎么办？**

检查 Redis 连接，确认 `CELERY_BROKER_DB` 和 Worker 使用同一配置：

```bash
docker compose logs schedule-worker
```

**Q: 数据库连接失败？**

等待 MySQL 健康检查通过（约 30 秒），或手动运行迁移：

```bash
docker compose exec schedule-api alembic upgrade head
```

**Q: 上游服务不可用时如何测试？**

`scheduler_tasks.py` 中的 `_fetch_upstream_data()` 已内置 fallback stub 数据，上游不可用时自动使用 stub，不影响本组功能开发。
