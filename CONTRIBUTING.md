# 贡献指南 — 自动排课组开发工作流

> 阅读本文档约需 5 分钟。开始第一个任务前请完整读完。

---

## 目录

1. [整体工作流概览](#1-整体工作流概览)
2. [环境准备](#2-环境准备)
3. [领取 Issue 并开始开发](#3-领取-issue-并开始开发)
4. [后端开发规范](#4-后端开发规范)
5. [前端开发规范](#5-前端开发规范)
6. [测试人员工作流](#6-测试人员工作流)
7. [提交 PR 与 Code Review](#7-提交-pr-与-code-review)
8. [集成测试与版本发布](#8-集成测试与版本发布)
9. [通用规范](#9-通用规范)

---

## 1. 整体工作流概览

```
需求/Issue
    │
    ▼
领取 Issue → 创建分支
    │
    ├─── 后端 ──→ mock数据开发 → 单元测试通过 → PR
    │
    ├─── 前端 ──→ mock数据开发 ──────────────→ PR
    │
    └─── 测试 ──→ 边界用例测试 → CI云端测试 → 发现Bug提Issue
                                                    │
                              PR → Code Review → 合并到 main
                                                    │
                                           定期集成测试 → 打 Tag
                                                    │
                                           自动构建镜像 → 推送镜像仓库
```

**核心原则：所有代码改动必须关联一个 Issue，禁止直接向 main 推送代码。**

---

## 2. 环境准备

### 2.1 克隆项目

```bash
git clone git@github.com:uppi7/zjuse-schedule.git
cd zjuse-schedule
```

### 2.2 启动开发环境

```bash
# 复制环境变量（首次）
cp .env.example .env

# 启动 MySQL + Redis + API + Worker（全部容器）
docker compose up --build

# 验证启动成功
curl http://localhost:8002/health
# 期望输出：{"status": "ok", "service": "automatic-course-arrangement"}
```

代码修改后 API 自动热重载（Uvicorn `--reload` 模式），无需重启容器。

> API 文档：http://localhost:8002/docs　　查看容器日志：`docker compose logs -f schedule-api`

---

## 3. 领取 Issue 并开始开发

### 3.1 从 Issue Board 领取任务

1. 打开 [Issue 列表](https://github.com/uppi7/zjuse-schedule/issues)
2. 选择标有 `ready` 的 Issue（`blocked` 的暂不可开始）
3. 将 Issue **assign 给自己**，表示已认领
4. 把 Issue 状态从 `ready` 改为 `in-progress`


### 3.2 创建功能分支

分支命名规范：`<type>/issue-<编号>-<简短描述>`

```bash
# 功能开发
git checkout -b feature/issue-3-classroom-crud

# Bug 修复
git checkout -b fix/issue-12-schedule-status-error

# 测试相关
git checkout -b test/issue-16-classroom-tests
```

| type | 使用场景 |
|---|---|
| `feature` | 新功能开发 |
| `fix` | Bug 修复 |
| `test` | 添加或修改测试 |
| `refactor` | 重构（不改变行为） |
| `docs` | 仅文档改动 |

### 3.3 Commit 规范

```
<type>(scope): <简短描述>

# 示例
feat(classroom): add classroom CRUD endpoints
fix(schedule): handle duplicate semester trigger correctly
test(classroom): add permission rejection tests
```

提交时在 commit message 或 PR 描述中引用 Issue：

```bash
git commit -m "feat(classroom): add CRUD endpoints

Closes #3"
```

---

## 4. 后端开发规范

### 4.1 用 Mock 数据独立开发

后端开发**不依赖前端进度**，也**不依赖上游服务**（基础信息组）。

上游不可用时，`app/tasks/scheduler_tasks.py` 中的 `_fetch_upstream_data()` 会自动 fallback 到 stub 数据，无需手动处理。

本地 API 调试用 Swagger UI：http://localhost:8002/docs

每个接口都需要在 Header 中携带认证信息：

```
X-User-Id: dev-admin-001
X-User-Role: ADMIN
```

### 4.2 代码结构约定

新功能按以下顺序添加，详细说明见 `docs/DEVELOPMENT_GUIDE.md`：

```
1. app/schemas/xxx.py       — 定义请求/响应 DTO
2. app/models/xxx.py        — 定义数据表（如需新表）
3. app/services/xxx_service.py  — 业务逻辑
4. app/api/v1/xxx.py        — 路由/接口
5. 在 app/main.py 注册路由
```

### 4.3 单元测试要求（PR 合并的门槛）

**后端 PR 合并前，必须有对应的单元测试且全部通过。**

```bash
pytest tests/ -v
```

测试文件放在 `tests/` 目录，参考 `tests/test_classrooms.py` 的写法。
每个 Issue 的验收标准中列出的场景，必须各有一个测试覆盖。

测试使用 SQLite 内存库，无需真实 MySQL：`tests/conftest.py` 已配置好。

---

## 5. 前端开发规范

### 5.1 项目结构

前端代码位于 `frontend/` 目录，技术栈：**Vue 3 + Vite**。

```
frontend/src/
├── api/index.js            # 统一 fetch 封装，含认证 Header 和 /api 路径
├── router/index.js         # 路由表（添加新页面在此注册）
├── App.vue                 # 顶部导航栏
├── style.css               # 全局样式
└── views/
    ├── ScheduleTrigger.vue # Issue #9：触发排课 + 进度条
    └── ScheduleEntries.vue # Issue #10：课表查询表格
```

`docker compose up --build` 启动后，前端服务自动运行于 **http://localhost:5173**，无需额外命令。

### 5.2 开发新页面

1. 在 `frontend/src/views/` 新建 `XxxPage.vue`
2. 在 `frontend/src/router/index.js` 添加路由：
   ```javascript
   { path: '/xxx', component: () => import('../views/XxxPage.vue') }
   ```
3. （可选）在 `frontend/src/App.vue` 导航栏里添加链接
4. 接口调用统一通过 `frontend/src/api/index.js`，按已有模式追加方法

### 5.3 接口调用规范

`src/api/index.js` 已封装认证 Header 和错误处理，直接调用即可：

```javascript
import { api } from '../api'

// 示例：触发排课
const res = await api.triggerSchedule('2024-2025-1')
const taskId = res.data.task_id

// 示例：查询课表
const res = await api.getEntries({ semester: '2024-2025-1', teacher_id: 'T001' })
```

**添加新接口调用**：在 `src/api/index.js` 的 `api` 对象中追加：

```javascript
export const api = {
  // ... 已有方法 ...
  getClassrooms: (params) =>
    request('GET', `/api/v1/classrooms?${new URLSearchParams(params)}`),
}
```

统一响应格式（所有接口）：

```typescript
interface ApiResponse<T> {
  code: number;    // 0 = 成功，非零 = 错误
  msg: string;
  data: T | null;
}
```

### 5.4 用 Mock 数据独立开发（后端未就绪时）

后端接口未完成时，用 [Apifox](https://apifox.com/) 生成 Mock Server：

1. 在 Apifox 导入 `http://localhost:8002/openapi.json`（后端启动后可访问）
2. 启用 Mock Server，得到形如 `http://127.0.0.1:4523/m1/...` 的地址
3. 临时修改 `frontend/src/api/index.js` 顶部：
   ```javascript
   const BASE = 'http://127.0.0.1:4523/m1/...'   // 临时 mock 地址
   // 将 fetch(path, ...) 改为 fetch(BASE + path, ...)
   ```
   联调完成后改回。也可以通过修改 `vite.config.js` 的 proxy target 实现，无需改业务代码。

---

## 6. 测试人员工作流

### 6.1 日常任务

1. **领取测试类 Issue**（标有 `test` label）
2. **针对已完成的后端接口编写高强度测试**：正常场景 + 边界值 + 异常场景
3. **编写 CI 云端测试**（见 6.2）
4. **发现 Bug 时提 Bug Issue**（使用 Bug 模板，见下方）

### 6.2 测试场景覆盖要求

每个接口至少覆盖：

| 场景类型 | 示例 |
|---|---|
| 正常场景 | 合法入参，期望返回 200 + 正确数据 |
| 权限拦截 | 低权限角色调用写接口，期望 403 |
| 无认证 | 不带 Header，期望 401 |
| 不存在资源 | 查询不存在的 ID，期望 404 |
| 重复操作 | 重复创建同 code 教室，期望 409 |
| 参数越界 | 容量填负数、节次超过12，期望 422 |

### 6.3 提 Bug Issue

发现 Bug 时，在 Issue Board 新建 Issue 并选择 **Bug Report 模板**，填写：

- 复现步骤（curl 命令或具体操作）
- 期望结果 vs 实际结果
- 相关日志（`docker compose logs schedule-api`）

---

## 7. 提交 PR 与 Code Review

### 7.1 提交 PR 前的 Checklist

```
□ 本地 pytest tests/ -v 全部通过
□ commit message 符合规范，包含 Closes #<issue号>
□ 没有提交 .env 文件或包含密码的内容
□ 没有留下调试用的 print() 或 console.log()
□ PR 描述填写了"改动内容"和"测试方法"
```

### 7.2 PR 命名规范

```
feat(#3): add classroom CRUD endpoints
fix(#12): handle duplicate semester schedule trigger
test(#16): add classroom permission tests
```

### 7.3 Code Review 规则

- **任意一名组员 approve 即可合并**（不需要所有人）
- Reviewer 重点检查：
  - 接口是否符合 `docs/DATA_SCHEMA.md` 的约定
  - 是否有权限校验遗漏
  - 异常处理是否到位
- Review 评论分两级：
  - `[must]` — 必须修改才能 approve
  - `[nit]` — 可选优化，不影响 approve

### 7.4 合并策略

使用 **Squash and Merge**，保持 main 分支提交记录整洁。

---

## 8. 集成测试与版本发布

### 8.1 定期集成测试

每次向 main 合并后，需在本地运行完整集成测试：

```bash
# 启动完整环境
docker compose up --build -d

# 等待健康检查通过
sleep 10

# 运行完整测试套件
pytest tests/ -v --tb=short

# 手动执行排课全链路冒烟测试
bash tests/smoke_test.sh
```

### 8.2 打版本 Tag

集成测试通过后，在 main 上打 Tag：

```bash
git tag v0.1.0 -m "排课触发与查询基础功能"
git push origin v0.1.0
```

Tag 命名规范：`v<major>.<minor>.<patch>`

| 版本号位 | 触发条件 |
|---|---|
| patch (+0.0.1) | Bug 修复、小改动 |
| minor (+0.1.0) | 新增完整功能模块（对应一个 Milestone） |
| major (+1.0.0) | 破坏性改动或全系统联调完成 |

### 8.3 镜像构建与推送

打 Tag 后，手动执行镜像构建（CI 自动化后无需手动）：

```bash
# 构建镜像
docker build -t schedule-api:v0.1.0 .

# 推送到 GitHub Container Registry
docker tag schedule-api:v0.1.0 ghcr.io/uppi7/schedule-api:v0.1.0
docker push ghcr.io/uppi7/schedule-api:v0.1.0
```

---

## 9. 通用规范

1. **所有开发工作必须关联 Issue**，无 Issue 的代码改动不予合并
2. **数据库/Redis 镜像仅用于本组本地测试**，不向大组提交这部分配置
3. **文档产出同步到飞书知识库**，代码内的 `docs/` 目录保留技术规范类文档
4. **禁止直接 push 到 main**，所有改动走 PR 流程
5. **Issue 模板已预设**，提 Issue 时填空即可，不要删除模板结构
