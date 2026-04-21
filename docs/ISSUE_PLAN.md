# GitHub Issue 规划 — 自动排课组

> 本文档列出所有需要发布的 Issue。框架代码为骨架，实际运行中可能有硬编码、字段名错误、类型映射缺失等问题，需要组员接手确认并修复。

---

## Label 体系

| Label | 颜色建议 | 含义 |
|---|---|---|
| `backend` | 蓝色 | 后端逻辑、API、数据库 |
| `algorithm` | 紫色 | 排课算法引擎 |
| `frontend` | 绿色 | 前端页面、API 调用 |
| `test` | 橙色 | 测试用例 |
| `devops` | 灰色 | Docker、CI |
| `cross-team` | 青色 | 需与其他组联调或协商 |
| `bug` | 红色 | 框架中已发现的错误，需修复 |
| `ready` | 深绿 | 可立即开工 |
| `blocked` | 暗红 | 等待跨组结果，暂不可开始 |

## Milestone 划分

| Milestone | 目标 |
|---|---|
| **M0** | Docker 本地环境跑通，全服务健康 |
| **M1** | 核心接口可用，全链路端到端联通（含 DB 写入） |
| **M2** | 真实排课算法上线，满足硬约束 |
| **M3** | 跨组联调完成，前端接入网关认证 |
| **M4** | 主要场景有自动化测试覆盖（可与 M1–M3 并行推进） |

---

## Issue 清单

---

### M0：基础设施就绪

**#1 · 验证 Docker Compose 五服务健康启动** `devops` `ready`
- 背景：验证任何组员执行 `make build` 能得到可用的开发环境。
- 验收标准：
  - [ ] `mysql`、`redis`、`schedule-api`、`schedule-worker`、`schedule-frontend` 五个容器均为 `healthy` 或 `running`
  - [ ] `make health` 返回 `{"status":"ok","service":"automatic-course-arrangement"}`
  - [ ] Celery Worker 日志出现 `ready` 字样（`make logs-worker`）
  - [ ] 访问 `http://localhost:5173` 能看到前端页面（路由正常）
  - [ ] `classrooms`、`schedule_tasks`、`schedule_entries` 三张表自动存在（`make db` 进入 MySQL 确认）
- 实现提示：建表逻辑在 `app/core/database.py → init_db()`，由 `app/main.py` lifespan 调用；Docker 配置在 `docker-compose.yml`

---

### M1：核心接口验证与补全

**#2 · 验证教室 CRUD 接口全链路** `backend` `ready`
- 背景：教室路由（`app/api/v1/classrooms.py`）和 service（`app/services/classroom_service.py`）框架已写好，但从未在真实 Docker 环境中跑通过，可能存在框架配置问题或边界情况遗漏。
- 验收标准：
  - [ ] `POST /api/v1/classrooms` 成功创建教室，重复 code 返回 409
  - [ ] `GET /api/v1/classrooms` 返回列表，skip/limit 分页正确
  - [ ] `GET /api/v1/classrooms/{id}` 返回单条，不存在时返回 404
  - [ ] `PATCH /api/v1/classrooms/{id}` 更新字段后查询可见
  - [ ] `DELETE /api/v1/classrooms/{id}` 删除后查询返回 404
  - [ ] 非 ADMIN Header 调用写接口返回 403，无 Header 返回 401
- 实现提示：用 curl 或 Swagger UI（`http://localhost:8002/docs`）调用，Header 填 `X-User-Id: dev-admin-001 X-User-Role: ADMIN`；发现问题直接修复 `classrooms.py` 或 `classroom_service.py`

---

**#3 · 验证排课 API 全链路** `backend` `ready`
- 背景：排课触发、进度查询、手动调课、课表查询四个路由（`app/api/v1/schedule.py` + `app/services/schedule_service.py`）框架已写好，需在 Docker 环境中验证全链路通畅，并检查是否有硬编码或字段遗漏。
- 验收标准：
  - [ ] `POST /api/v1/schedule/auto-schedule` 立即返回 `task_id`（< 200ms），`make logs-worker` 出现对应任务
  - [ ] `GET /api/v1/schedule/schedule-status/{task_id}` 返回正确的 `status`、`progress`、`message` 字段（注意字段名，非 `meta`）
  - [ ] 重复触发同一学期返回 409
  - [ ] `GET /api/v1/schedule/entries?semester=2024-2025-1` 返回空数组而非 404 或报错
  - [ ] `POST /api/v1/schedule/manual-adjust` 传入不存在的 `entry_id` 返回 404
  - [ ] 非 ADMIN 调用 trigger 和 manual-adjust 返回 403
- 实现提示：此时 `_save_results` 是空的，entries 始终为空是正常现象；重点验证链路本身不报错；参考 `CONTRIBUTING.md §4.3` 的 curl 示例

---

**#4 · 实现排课结果写入 MySQL（`_save_results`）** `backend` `ready`
- 背景：`app/tasks/scheduler_tasks.py → _save_results()` 当前为空 `pass`，是整个链路中唯一缺失的关键实现——触发可用、算法可用，但结果不落库，`/entries` 接口永远返回空。
- 验收标准：
  - [ ] 排课任务完成后，`schedule_entries` 表中有记录，`course_id`、`teacher_id`、`classroom_id`、`day_of_week` 等字段正确（`make db` 确认）
  - [ ] `schedule_tasks` 表中对应任务状态更新为 `SUCCESS`，`result_summary` 字段有内容
  - [ ] 任务失败时，`schedule_tasks.status` 更新为 `FAILED`，`error_msg` 有错误信息
  - [ ] 重跑同一学期任务不重复插入（幂等，或先删后插）
- 实现提示：在 `scheduler_tasks.py → _save_results(semester, results)` 中实现；在 Celery 任务里用 `asyncio.run()` 创建临时 DB session（参考同文件 `_fetch_upstream_data` 的模式），不能用 FastAPI 的 `get_db` 依赖；`results` 目前是 dict 列表（来自 `_build_stub_results`），写入 `ScheduleEntry` 时注意字段映射（参考 `app/models/schedule.py`）；`ScheduleEntry.classroom_id` 是外键，对应 `classrooms.id`

---

**#5 · 从本地 DB 查询教室数据（含类型映射）** `backend` `ready`
- 背景：`_fetch_upstream_data()` 中教室列表为硬编码单条记录 `[{"classroom_id": 1, "capacity": 120, "is_lab": False}]`，导致算法只能看到一间普通教室、实验室约束永远无法生效。
- 验收标准：
  - [ ] `_fetch_upstream_data()` 中教室列表从 `classrooms` 表查询
  - [ ] 返回数据中 `is_lab` 字段正确映射：`room_type == "LAB"` → `is_lab=True`，其余类型 → `False`
  - [ ] `classroom_id` 使用 `Classroom.id`（DB 主键），与 `ScheduleEntry.classroom_id` 外键一致
  - [ ] 本地 DB 无教室数据时，任务状态更新为 `FAILED`，错误信息明确
- 实现提示：`Classroom` model 在 `app/models/classroom.py`，`room_type` 枚举值为 `LECTURE/LAB/GYM/MULTIMEDIA`；在 Celery 任务中用 `asyncio.run()` 和临时 session 执行 `select(Classroom).where(Classroom.is_active == True)`；需将结果转换为算法所需的 `ClassroomInput` 格式

---

**#6 · 修复前端进度状态字段名错误** `frontend` `bug` `ready`
- 背景：`frontend/src/views/ScheduleTrigger.vue` 中有两处字段名与后端 `ScheduleStatusResponse` 不匹配，导致进度文字永远不更新、完成提示显示"?"。
- 具体错误：
  - `ScheduleTrigger.vue:42`：`statusText.value = d.meta ?? d.status` — 后端无 `meta` 字段，应为 `d.message ?? d.status`
  - `ScheduleTrigger.vue:47`：`d.result_summary?.total_entries` — 应为 `d.result_summary?.scheduled`
- 验收标准：
  - [ ] 排课任务运行期间，进度文字（如"正在运行排课算法..."）正确显示
  - [ ] 排课完成后提示文字正确显示已排课数量（非"?"）
- 实现提示：只需修改 `ScheduleTrigger.vue` 两处；后端字段定义在 `app/schemas/schedule.py → ScheduleStatusResponse`；`result_summary` 结构参考 `scheduler_tasks.py → run_auto_schedule` 返回值

---

**#17 · `semester` 参数格式校验** `backend` `ready`
- 背景：`AutoScheduleRequest.semester` 当前仅为 `str`，传入任意字符串（如 `"abc"`）都能触发排课任务，浪费 Celery 资源且错误信息不友好。
- 验收标准：
  - [ ] 传入格式正确的 semester（如 `"2024-2025-1"`）正常触发，返回 200
  - [ ] 传入格式错误的 semester（如 `"abc"`、`"2024-2025-3"`）返回 422，不创建 Celery 任务
- 实现提示：在 `app/schemas/schedule.py → AutoScheduleRequest.semester` 加 Pydantic regex 约束：`Field(..., pattern=r"^\d{4}-\d{4}-[12]$")`；一行修改

---

### M2：算法替换

**#7 · 实现排课算法核心逻辑并接入 Celery 任务** `algorithm` `backend` `ready`
- 背景：`app/algorithm/engine.py → run_schedule()` 当前为随机分配 stub，不检查冲突；`scheduler_tasks.py` 中 Step 2 仍调用 `_build_stub_results()` 而非真实算法，两处均需修改。
- 验收标准：
  - [ ] 硬约束1：同一教师同一时间段不出现两门课
  - [ ] 硬约束2：同一教室同一时间段不出现两门课
  - [ ] 硬约束3：教室容量 ≥ 课程选课人数
  - [ ] 硬约束4：实验课（`needs_lab=True`）只分配至实验室（`is_lab=True`）教室
  - [ ] `run_schedule` 函数签名保持不变：`(courses, classrooms, teachers) -> (list[ScheduleResult], list[str])`
  - [ ] `scheduler_tasks.py` Step 2 中 `_build_stub_results` 和 `time.sleep(5)` 替换为 `run_schedule(...)` 实际调用
  - [ ] 用 stub 数据（5 门课、3 间教室）能得到无冲突的排课结果
- 实现提示：算法修改只在 `app/algorithm/engine.py`；Celery 接入修改 `scheduler_tasks.py` Step 2；算法为纯同步 Python，不能用 `async`；可用贪心、回溯、遗传算法
- 依赖：#4（需 `_save_results` 实现后才能验证结果是否落库）

---

**#8 · 集成算法进度汇报** `algorithm` `backend` `ready`
- 背景：算法运行期间 Celery 任务进度卡在 30%，前端进度条不动。需要算法定期回调更新进度。
- 验收标准：
  - [ ] 算法运行期间进度从 30% 均匀增长至 70%（至少每处理 20% 的课程更新一次）
  - [ ] 进度消息文字有意义，如"已排课 X/Y 门"
- 实现提示：在 `scheduler_tasks.py → run_auto_schedule` 中构造 `progress_callback = lambda p, msg: self.update_state(...)` 传入 `run_schedule()`；修改 `engine.py` 中 `run_schedule` 签名，增加 `progress_callback: Callable[[int, str], None] | None = None` 参数
- 依赖：#7

---

### M3：跨组联调

**#9 · 替换信息服务 fallback stub（接入真实数据）** `backend` `cross-team` `blocked`
- 背景：`_fetch_upstream_data()` 用 try/except 包裹，上游不可用时降级为 stub 数据（1 位教师、1 门课），掩盖联调问题。httpx client 的事件循环问题**框架中已修复**（每次调用创建临时 `async with httpx.AsyncClient`）；本 Issue 的工作是：上游就绪后移除降级分支，让排课任务使用真实数据。
- API 约定：`GET http://info-service:8000/api/v1/teachers`（字段：`teacher_id`、`name`）；`GET http://info-service:8000/api/v1/courses`（字段：`course_id`、`teacher_id`、`weekly_hours`、`student_count`、`needs_lab`）；外层均为 `{"code":0,"data":[]}`。
- 验收标准：
  - [ ] 排课任务使用真实 HTTP 请求拉取教师和课程数据
  - [ ] 上游不可用时任务状态更新为 `FAILED`，不再静默降级
  - [ ] 与第一组联调成功，拉取到真实数据并完成一次排课
- 实现提示：修改 `_fetch_upstream_data()` — 移除 `except Exception` 的 fallback 分支；`InfoServiceClient`（`app/core/external_clients.py`）封装了认证和路径，可直接使用，或沿用现有的内联 `httpx.AsyncClient` 模式

---

**#10 · 网关认证 Header 端到端验证** `backend` `cross-team` `ready`
- 背景：认证字段（`X-User-Id`、`X-User-Role`，角色枚举 `ADMIN`/`TEACHER`/`STUDENT`）已写入代码，需与网关联调确认实际流量中 Header 正确透传。
- 验收标准：
  - [ ] 经网关的请求携带正确 Header 时，接口正常返回 200/201
  - [ ] 无 Header 的请求返回 401
  - [ ] STUDENT 角色触发排课、创建教室返回 403
  - [ ] 与网关联调的行为与本地单测一致

---

**#11 · 验证下游选课组能拉取课表** `backend` `cross-team` `ready`
- 背景：课表交付方式为拉取 API，`GET /api/v1/schedule/entries?semester=...` 已实现。需与第三组联调确认字段满足需求。
- 验收标准：
  - [ ] 第三组通过 `GET /api/v1/schedule/entries?semester=2024-2025-1` 能成功拉取数据
  - [ ] `teacher_id`、`course_id` 筛选参数正常工作
  - [ ] 如需新增返回字段，修改 `app/schemas/schedule.py → ScheduleEntryOut`

---

**#12 · 前端接入网关认证（替换硬编码 Header）** `frontend` `cross-team` `blocked`
- 背景：`frontend/src/api/index.js` 开发阶段硬编码了 `X-User-Id: dev-admin-001`、`X-User-Role: ADMIN`。上线前需替换为网关透传或登录态实际值，否则生产环境无法使用真实权限控制。
- 验收标准：
  - [ ] `api/index.js` 中 `AUTH_HEADERS` 不再硬编码 user_id 和 role
  - [ ] Header 值来源于网关透传或前端登录态（具体方式与网关组协商）
  - [ ] 不同角色用户访问页面，后端权限拦截行为正确
- 实现提示：需先与第二（网关）组确认前端如何获取认证信息（Cookie、LocalStorage、或由网关直接注入）

---

### M4：测试完备（可与 M1–M3 并行推进）

**#13 · 排课异步链路集成测试** `test` `ready`
- 背景：当前没有覆盖"触发排课 → Celery 接收 → 结果写库"完整链路的自动化测试，是最核心的集成缺口。
- 验收标准：
  - [ ] 触发排课后，`schedule_tasks` 表中有记录，`celery_task_id` 不为空
  - [ ] 任务完成后，`schedule_entries` 表中有记录
  - [ ] 重复触发同一学期返回 409
  - [ ] 查询不存在的 `task_id` 返回 PENDING 状态（非报错）
- 实现提示：Celery 任务在测试中建议设置 `CELERY_TASK_ALWAYS_EAGER=True` 同步执行，或直接单测 service 层（`schedule_service.trigger_auto_schedule`）；`conftest.py` 中 fixture 已就绪（SQLite 内存库）
- 依赖：#4（`_save_results` 实现后才能断言 entries 写入）

---

**#14 · 手动调课与课表查询测试** `test` `ready`
- 背景：手动调课（`PATCH`）和课表查询（`GET /entries`）的过滤逻辑当前无测试覆盖，边界情况（空结果、非法参数、权限）未验证。
- 验收标准：
  - [ ] 手动调课后，修改字段在 `GET /entries` 中可见
  - [ ] 传入不存在的 `entry_id` 返回 404
  - [ ] 非 ADMIN 角色调课返回 403
  - [ ] `semester`、`teacher_id`、`course_id` 三个筛选参数各有一个正确过滤的用例
  - [ ] 无数据时返回空数组（200），不返回 404

---

**#15 · 补全教室 CRUD 测试** `test` `ready`
- 背景：`tests/test_classrooms.py` 已有创建、列表、409、学生 403 四个用例；缺少更新、删除及完整权限覆盖。
- 验收标准：
  - [ ] `PATCH /classrooms/{id}` 更新成功，响应字段正确
  - [ ] `DELETE /classrooms/{id}` 删除后查询返回 404
  - [ ] 非 ADMIN 调用更新、删除均返回 403

---

**#16 · 权限矩阵专项测试** `test` `ready`
- 背景：接口有三种角色（ADMIN / TEACHER / STUDENT），现有测试零散，缺乏系统性覆盖。如果框架权限配置有遗漏（如某写接口忘记 `require_admin` 依赖），只有权限矩阵测试才能统一揪出。
- 验收标准：
  - [ ] STUDENT 触发排课（`POST /auto-schedule`）返回 403
  - [ ] STUDENT 手动调课（`POST /manual-adjust`）返回 403
  - [ ] STUDENT 创建/更新/删除教室返回 403
  - [ ] 无认证 Header 的所有接口返回 401
  - [ ] ADMIN 可正常操作以上所有接口
- 实现提示：`conftest.py` 已有 `student_client` fixture，可直接使用

---

## 认领建议

| 如果你是… | 建议先领取的 Issue |
|---|---|
| 任何人（入门首选） | **#1**（跑通环境）→ **#2** 或 **#3**（接口冒烟） |
| 后端（熟悉 SQLAlchemy） | **#4**（核心空缺）→ **#5**（教室数据）→ **#17**（一行校验） |
| 后端（熟悉 Celery） | **#4** → **#3**（全链路验证）→ **#8**（配合算法进度回调） |
| 前端 | **#6**（立即可修的 bug）→ **#3**（联调验证） |
| 算法组 | **#7**（算法 + Celery 接入）→ **#8** |
| 测试 | **#16** → **#15** → **#14**（可与后端并行）；**#13** 等 #4 合并后开始 |
| 跨组联调 | **#10**、**#11** 可立即开始；**#9**、**#12** 等对应组就绪后开始 |

> 一个 Issue 同时只由一人认领（assign）。预计超过 2 天工作量的建议拆子 Issue。
