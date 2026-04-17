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
| **M3：跨组联调** | 与第一、三组对接完毕 | 依赖协商结论，`blocked` Issue 解锁后开始 |
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
（可选：前置 Issue 编号，或"需等待协商结论 X-X"）
```

---

## 二、Issue 清单

> 按 Milestone 排列，同一 Milestone 内优先级从高到低。
> 带 🔒 的 Issue 需等待跨组协商结论，先建 Issue、打 `blocked` 标签，协商完成后去掉 `blocked` 加 `ready`。

---

### M0：基础设施就绪

**#1 · 完成数据库初始迁移**
- Label: `backend` `devops` `ready`
- 背景：框架已有 SQLAlchemy 模型，需要初始化 Alembic 并生成首次迁移脚本，使 `docker compose up` 后表结构自动就绪。
- 验收标准：
  - [ ] 执行 `alembic upgrade head` 后，`classrooms`、`schedule_tasks`、`schedule_entries` 三张表存在
  - [ ] `docker-compose.yml` 中 `schedule-api` 启动时自动执行迁移（或写入启动脚本）
- 实现提示：`alembic init alembic`，在 `env.py` 中引入 `app.core.database.Base`

---

**#2 · 验证 Docker Compose 四服务全部健康启动**
- Label: `devops` `ready`
- 背景：保证任何组员拉代码后执行 `docker compose up --build` 能得到一个可用的开发环境。
- 验收标准：
  - [ ] `mysql`、`redis`、`schedule-api`、`schedule-worker` 四个容器均为 `healthy` 或 `running`
  - [ ] `curl http://localhost:8002/health` 返回 `{"status": "ok"}`
  - [ ] Celery Worker 日志中出现 `ready` 字样，无报错

---

### M1：核心接口可用

**#3 · 实现教室创建与列表接口**
- Label: `backend` `ready`
- 背景：框架已有路由和 service 骨架，需补全 Alembic 迁移后的实际联调验证，并处理边界情况。
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
  - [ ] 状态变为 SUCCESS 时，停止轮询并跳转/提示"排课完成"
  - [ ] 状态变为 FAILED 时，显示错误信息
- 实现提示：轮询 `GET /api/v1/schedule/schedule-status/{task_id}`，当 `status === "SUCCESS"` 时停止

---

**#10 · 前端：实现课表展示页面**
- Label: `frontend` `ready`
- 背景：展示排课结果，支持按学期、教师筛选，以表格或课程表视图呈现。
- 验收标准：
  - [ ] 默认展示当前学期课表
  - [ ] 支持按教师筛选
  - [ ] 每条记录显示：课程名、教师、教室、星期、节次、周次范围

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

**#13 🔒 · 对接基础信息组：替换教师/课程数据拉取逻辑**
- Label: `backend` `blocked`
- 背景：当前 `_fetch_upstream_data()` 使用 stub 数据，需等待协商结论（议题 1-A、1-B）后替换为真实调用。
- 解锁条件：议题 1-A、1-B 协商完成（URL 和 JSON 结构已确认）
- 验收标准：
  - [ ] 排课任务从基础信息组实际拉取教师列表
  - [ ] 排课任务从基础信息组实际拉取课程列表
  - [ ] 上游服务不可用时，任务状态更新为 FAILED，错误码为 2005

---

**#14 🔒 · 对接网关：更新认证 Header 字段名**
- Label: `backend` `blocked`
- 背景：`X-User-Id`、`X-User-Role` 为占位值，需等待协商结论（议题 1-C）后更新。
- 解锁条件：议题 1-C 协商完成
- 验收标准：
  - [ ] 使用正式 Header 字段名后，所有需要认证的接口均返回 200（而非 401）
  - [ ] 无 Header 时仍返回 401
  - [ ] 更新 `.env.example` 中的默认值

---

**#15 🔒 · 对接选课组：实现排课完成通知**
- Label: `backend` `blocked`
- 背景：`notify_downstream()` 目前为空实现，需等待协商结论（议题 2-A）后实现真正的通知逻辑。
- 解锁条件：议题 2-A 协商完成（确定方案 A 还是方案 B）
- 验收标准（方案 A）：
  - [ ] 选课组能通过 `GET /api/v1/schedule/entries` 成功拉取数据
- 验收标准（方案 B）：
  - [ ] 排课完成后，MQ 中出现事件消息，格式与约定一致

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
| 任何人 | #13、#14、#15 等协商结束即可开始 |

> 一个 Issue 同时只由一人认领（assign）。如果预计工作量超过 2 天，建议拆成子 Issue。
