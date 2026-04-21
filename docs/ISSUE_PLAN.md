# GitHub Issue 规划指南 — 自动排课组

> 本文档说明 Issue 的拟定规范，并列出需要创建的全部 Issue。
> 开发和测试人员进入仓库后，按 Label 筛选自己感兴趣的 Issue 并 assign 给自己即可开始工作。

---

## 一、Issue 规范

### Label 体系

创建仓库后先建立以下 Label：

| Label | 颜色建议 | 含义 |
|---|---|---|
| `backend` | 蓝色 | 后端逻辑、API、数据库 |
| `algorithm` | 紫色 | 排课算法引擎 |
| `frontend` | 绿色 | 前端对接、联调 |
| `test` | 橙色 | 测试用例、自动化测试 |
| `devops` | 灰色 | Docker、CI、部署 |
| `blocked` | 红色 | 阻塞于跨组协商结果，暂不可开始 |
| `ready` | 深绿 | 依赖已解决，可以立即开工 |
| `in-progress` | 黄色 | 有人正在做 |

### Milestone 划分

| Milestone | 目标 | 说明 |
|---|---|---|
| **M0：基础设施就绪** | 本地能跑通 | Docker 启动、DB 建表、健康检查通过 |
| **M1：核心接口可用** | 排课流程跑通（用 stub 数据） | 触发排课 → 查进度 → 查课表 全链路 |
| **M2：算法替换** | 真实算法上线 | stub 替换为真实排课逻辑 |
| **M3：跨组联调** | 与第一、三组对接完毕 | 协商已完成，API 地址和字段约定已落定，可直接开始 |
| **M4：测试完备** | 主要场景有自动化测试覆盖 | 可与 M1/M2 并行推进 |

### Issue 正文模板

```
## 背景
（为什么要做这个 Issue，一两句话）

## 验收标准
- [ ] 条件1
- [ ] 条件2
- [ ] 条件3

## 实现提示
（可选：指向具体文件、函数或设计决策）

## 依赖
（可选：前置 Issue 编号，或"无依赖"）
```

---

## 二、Issue 清单

> 按 Milestone 排列，同一 Milestone 内优先级从高到低。
> 所有 Issue 当前均已 `ready`，可直接认领开始。

---

### M0：基础设施就绪

**#1 · 验证数据库自动建表**
- Label: `backend` `devops` `ready`
- 背景：API 启动时通过 `Base.metadata.create_all` 自动建表，无需手动执行迁移命令。
- 验收标准：
  - [ ] 执行 `docker compose up --build` 后，`classrooms`、`schedule_tasks`、`schedule_entries` 三张表自动存在
  - [ ] 重复启动不会报错（`create_all` 已存在则跳过）
- 实现提示：逻辑已在 `app/core/database.py → init_db()`，由 `app/main.py` 的 lifespan 调用

---

**#2 · 验证 Docker Compose 五服务全部健康启动**
- Label: `devops` `ready`
- 背景：保证任何组员拉代码后执行 `docker compose up --build` 能得到一个可用的开发环境。
- 验收标准：
  - [ ] `mysql`、`redis`、`schedule-api`、`schedule-worker`、`schedule-frontend` 五个容器均为 `healthy` 或 `running`
  - [ ] `curl http://localhost:8002/health` 返回 `{"status": "ok"}`
  - [ ] Celery Worker 日志中出现 `ready` 字样，无报错
  - [ ] 访问 `http://localhost:5173` 能看到前端页面

---

### M1：核心接口可用

**#3 · 实现教室创建与列表接口**
- Label: `backend` `ready`
- 背景：框架已有路由和 service 骨架，需补全实际联调验证并处理边界情况。
- 验收标准：
  - [ ] `POST /api/v1/classrooms` 成功创建教室，重复 code 返回 409
  - [ ] `GET /api/v1/classrooms` 返回列表，支持 `skip`/`limit` 分页
  - [ ] 非 ADMIN 角色调用写接口返回 403
- 实现提示：主要逻辑已在 `app/services/classroom_service.py`，重点是联调测试

---

**#4 · 实现触发排课接口（异步链路）**
- Label: `backend` `ready`
- 背景：`POST /api/v1/schedule/auto-schedule` 是整个系统的核心入口，需要验证"触发 → Celery 接收 → Redis 状态更新"全链路通畅。
- 验收标准：
  - [ ] 调用接口立即返回 `task_id`（响应时间 < 200ms）
  - [ ] Celery Worker 日志中出现对应任务 ID
  - [ ] 重复触发同一学期返回 409
- 实现提示：`app/api/v1/schedule.py` → `app/services/schedule_service.py` → `app/tasks/scheduler_tasks.py`

---

**#5 · 实现排课进度查询接口**
- Label: `backend` `ready`
- 背景：前端需要通过轮询实时展示进度条，接口从 Redis 读取 Celery 任务状态。
- 验收标准：
  - [ ] 任务运行中时，`progress` 字段随时间增长（0→100）
  - [ ] 任务完成后，`status` 为 `SUCCESS`，`result_summary` 有数据
  - [ ] 查询不存在的 `task_id` 时，返回合理的状态（PENDING）而非报错
- 实现提示：`app/services/schedule_service.py` → `get_schedule_status()`，基于 `celery.result.AsyncResult`

---

**#6 · 实现排课结果写入 MySQL**
- Label: `backend` `ready`
- 背景：当前 `scheduler_tasks.py` 中 `_save_results()` 为空占位，需要实现真实的 DB 写入逻辑。
- 验收标准：
  - [ ] 排课任务完成后，`schedule_entries` 表中有对应记录
  - [ ] `schedule_tasks` 表中的任务状态更新为 `SUCCESS` 或 `FAILED`
  - [ ] 任务失败时，`error_msg` 字段有错误信息

---

**#7 · 实现课表查询接口**
- Label: `backend` `ready`
- 背景：`GET /api/v1/schedule/entries` 是下游选课组的数据来源，需要支持按学期/教师/课程筛选。
- 验收标准：
  - [ ] `?semester=2024-2025-1` 筛选正确
  - [ ] `?teacher_id=T001` 筛选正确
  - [ ] 两个参数组合使用正确
  - [ ] 无数据时返回空数组而非 404

---

**#8 · 实现手动调课接口**
- Label: `backend` `ready`
- 背景：教务管理员可以对已生成的课表进行人工微调。
- 验收标准：
  - [ ] 修改 `classroom_id` / `day_of_week` / `slot_start` 等字段后，DB 记录更新
  - [ ] 传入不存在的 `entry_id` 返回 404
  - [ ] 非 ADMIN 角色调用返回 403

---

**#9 · 前端：实现触发排课与进度条页面**
- Label: `frontend` `ready`
- 背景：管理员操作入口，调用 `POST /auto-schedule` 后展示实时进度条直到完成。
- 验收标准：
  - [ ] 点击"触发排课"后，按钮变为禁用，进度条出现
  - [ ] 每 3 秒轮询一次进度，进度条实时更新
  - [ ] 状态变为 SUCCESS 时，停止轮询并提示"排课完成"
  - [ ] 状态变为 FAILED 时，显示错误信息
  - [ ] 重复触发同一学期时，界面提示 409 错误而非崩溃
- 实现提示：骨架已在 `frontend/src/views/ScheduleTrigger.vue`，接口调用封装在 `frontend/src/api/index.js → api.triggerSchedule / api.getScheduleStatus`

---

**#10 · 前端：实现课表展示页面**
- Label: `frontend` `ready`
- 背景：展示排课结果，支持按学期、教师筛选，以表格或课程表视图呈现。
- 验收标准：
  - [ ] 默认展示当前学期课表
  - [ ] 支持按教师ID、课程ID筛选
  - [ ] 每条记录显示：课程ID、教师ID、教室ID、星期、节次、周次范围
  - [ ] 无数据时显示友好提示，不显示空表格
- 实现提示：骨架已在 `frontend/src/views/ScheduleEntries.vue`，接口调用封装在 `frontend/src/api/index.js → api.getEntries`

---

### M2：算法替换

**#11 · 实现排课算法核心逻辑**
- Label: `algorithm` `ready`
- 背景：`app/algorithm/engine.py` 中 `run_schedule()` 目前为随机 stub，需替换为满足硬约束的真实算法。
- 验收标准：
  - [ ] 硬约束1：同一教师同一时间段不出现两门课
  - [ ] 硬约束2：同一教室同一时间段不出现两门课
  - [ ] 硬约束3：教室容量 ≥ 课程选课人数
  - [ ] 硬约束4：实验课只分配至实验室类型教室
  - [ ] 函数签名与现有接口保持一致（不修改入参/返回值类型）
- 实现提示：只需修改 `app/algorithm/engine.py`，不需要碰其他文件；算法为纯同步 Python，不能用 `async`

---

**#12 · 算法进度汇报集成**
- Label: `algorithm` `backend` `ready`
- 背景：算法运行时需定期调用 `self.update_state()` 更新进度，让前端进度条不卡在某个百分比。
- 验收标准：
  - [ ] 算法运行过程中，每处理完约 20% 的课程更新一次进度
  - [ ] 进度消息文字有意义（如"已排课 X/Y 门"）
- 实现提示：在 `scheduler_tasks.py` 的 `run_auto_schedule` 任务中，将进度回调传入算法

---

### M3：跨组联调

**#13 · 对接基础信息组：替换教师/课程数据拉取逻辑**
- Label: `backend` `ready`
- 背景：当前 `_fetch_upstream_data()` 使用 fallback stub 数据。API 地址和字段格式已与第一组确认，可直接对接。
- 约定：`GET http://info-service:8000/api/v1/teachers`（字段：`teacher_id`、`name`）；`GET http://info-service:8000/api/v1/courses`（字段：`course_id`、`teacher_id`、`weekly_hours`、`student_count`、`needs_lab`）；外层均为 `{"code":0,"data":[...]}`。
- 验收标准：
  - [ ] 排课任务从基础信息组实际拉取教师列表并正确解包字段
  - [ ] 排课任务从基础信息组实际拉取课程列表并正确解包字段
  - [ ] 上游服务不可用时，任务状态更新为 FAILED，错误码为 2005
- 实现提示：修改 `app/tasks/scheduler_tasks.py` → `_fetch_upstream_data()`，移除 fallback 分支

---

**#14 · 对接网关：端到端验证认证 Header**
- Label: `backend` `ready`
- 背景：认证 Header 字段名（`X-User-Id` / `X-User-Role`）和角色枚举（`ADMIN` / `TEACHER` / `STUDENT`）已与网关负责人确认并写入代码，需做全链路验证。
- 验收标准：
  - [ ] 携带正确 Header 的请求正常返回（200 / 201）
  - [ ] 无 Header 的请求返回 401
  - [ ] STUDENT 角色调用写接口返回 403
  - [ ] 与网关联调时行为与单测一致

---

**#15 · 对接选课组：验证课表拉取接口**
- Label: `backend` `ready`
- 背景：下游交付方式已确定为拉取 API。`GET /api/v1/schedule/entries` 已实现，需与第三组联调验证字段满足需求。
- 验收标准：
  - [ ] 第三组能通过 `GET /api/v1/schedule/entries?semester=...` 成功拉取数据
  - [ ] 返回字段满足选课组需求（如需新增字段，修改 `app/schemas/schedule.py` → `ScheduleEntryOut`）
  - [ ] 接口支持 `teacher_id`、`course_id` 筛选参数正常工作

---

### M4：测试完备

**#16 · 编写教室 CRUD 自动化测试**
- Label: `test` `ready`
- 验收标准：
  - [ ] 正常创建、查询、更新、删除各有一个 passing test
  - [ ] 重复 code 的 409 有测试
  - [ ] 权限拦截（403）有测试

---

**#17 · 编写排课异步链路集成测试**
- Label: `test` `ready`
- 背景：验证"触发 → Celery 接收 → 状态更新 → 结果写库"完整链路，是最核心的集成测试。
- 验收标准：
  - [ ] 触发排课后，最终 `status` 变为 `SUCCESS`
  - [ ] `schedule_entries` 表中有记录
  - [ ] 重复触发同一学期返回 409

---

**#18 · 编写手动调课与课表查询测试**
- Label: `test` `ready`
- 验收标准：
  - [ ] 手动调课后，字段变更在查询接口中可见
  - [ ] 各筛选参数正确过滤结果

---

**#19 · 编写权限拦截专项测试**
- Label: `test` `ready`
- 背景：排课组接口有角色区分，测试需覆盖 ADMIN/TEACHER/STUDENT 三种角色对各接口的访问结果。
- 验收标准：
  - [ ] STUDENT 角色触发排课、调课、创建教室均返回 403
  - [ ] 无 Header 的请求返回 401
  - [ ] ADMIN 角色可正常操作所有接口

---

## 三、认领建议

| 如果你是… | 建议先领取的 Issue |
|---|---|
| 后端（有 DB 经验） | #1 → #4 → #6 |
| 后端（有 FastAPI 经验） | #3 → #5 → #7 → #8 |
| 算法组 | #11 → #12 |
| 前端 | #9 → #10 |
| 测试 | #2 → #16 → #19（可与后端并行） |
| 任何人 | #13、#14、#15（跨组联调，可直接开始） |

> 一个 Issue 同时只由一人认领（assign）。如果预计工作量超过 2 天，建议拆成子 Issue。
