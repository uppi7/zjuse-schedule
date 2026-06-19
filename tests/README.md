# tests/ — 测试模块说明

排课系统的测试入口。采用 4 层架构，每层独立 marker、可单独触发；GitHub CI 只跑无需外部栈的 unit + solver，integration/e2e 由本地或 STSS-gateway 完整栈验收触发。

## 分层架构

| 层 | 路径 | marker | Owner | 命令 |
|---|---|---|---|---|
| **unit** | [tests/unit/](unit/) | `@pytest.mark.unit` | **feature 开发者**（各自写负责模块的单元测试） | `make test-unit` |
| **integration** | [tests/integration/](integration/) | `@pytest.mark.integration` | **专职测试** | `make test-integration` |
| **solver** | [tests/solver/](solver/) | `@pytest.mark.solver` | **专职测试** | `make test-solver` |
| **e2e** | [tests/e2e/](e2e/) | `@pytest.mark.e2e` / `smoke` | **专职测试** | `make test-e2e` |

---

## 各层详解

### unit 层

**负责范围**
进程内单元测试。用 `httpx.ASGITransport` 直接打 FastAPI 应用对象，配合 SQLite in-memory DB，**不依赖外部容器**。验证范围：路由、服务层、schema、工具函数的纯函数行为。

**框架**
- 全部 fixture 由根 [conftest.py](conftest.py) 提供：
  - `client` (ADMIN) / `student_client` (STUDENT) — 通过 `app.dependency_overrides` 注入测试 DB session
  - `db_session` — function 作用域，每个测试结束自动 rollback
  - `create_tables` — session autouse，自动建表/销毁
- 算法 dataclass 工厂：[factories.py](factories.py) 的 `make_course` / `make_classroom` / `make_preference` / `make_minimal_solver_input`

**添加新用例**
1. 文件放 [tests/unit/](unit/)，命名 `test_<模块>.py`
2. 文件顶部加 `pytestmark = pytest.mark.unit`
3. 测试函数声明 fixture 参数即注入：
   ```python
   async def test_xxx(client: AsyncClient):
       resp = await client.post("/api/v1/...", json={...})
       assert resp.status_code == 200
   ```
4. 跑：`make test-unit`

---

### integration 层

**负责范围**
跨服务集成测试。通过 [docker-compose.test.yml](../docker-compose.test.yml) 起隔离栈（MySQL 3308 / Redis 6381 / FastAPI 8003 / Celery worker），httpx 打**真实网络**，验证跨服务的链路：路由 → DB 持久化 → Celery 任务派发 → 状态汇报 → 结果落库。

**框架**
- [integration/conftest.py](integration/conftest.py) 提供：
  - `INTEGRATION_BASE_URL` — 默认 `http://localhost:8003`，可用环境变量覆盖
  - `integration_client` (ADMIN) / `integration_student_client` (STUDENT) — 30 秒超时
- 需要直连 MySQL/Redis 做白盒断言时，在本层 conftest 自行加 fixture（aiomysql / redis client）

**添加新用例**
1. 文件放 [tests/integration/](integration/)，命名 `test_<场景>.py`
2. 文件顶部加 `pytestmark = pytest.mark.integration`
3. 用 `integration_client` 发请求
4. 跑：`make test-integration`（自动起停 test 栈）

---

### solver 层

**负责范围**
对 [app/algorithm/engine.py](../app/algorithm/engine.py) 的 `run_schedule()` 做 golden case 回归。**纯 Python 调用**，不起docker。每个 case = 一组输入 JSON + 一组期望输出 JSON，参数化自动跑。

**框架**
- [solver/conftest.py](solver/conftest.py) 提供：
  - `SolverInput` / `SolverExpected` — case 数据包装 dataclass
  - `discover_golden_cases()` — 自动发现 `fixtures/golden/*/`，**会跳过下划线前缀目录**
  - `load_golden_case(case_dir)` — 读 JSON 反序列化为 dataclass，含 `available_slots` 的 list→set tuple 转换
  - `count_hard_conflicts(results)` — 教师/教室同时段冲突统计（粗粒度，未含 `week_parity` / `week_start-end`，tester 可按需扩展）
  - `assert_solver_result(...)` — 默认断言：scheduled 数 / unscheduled 集合 / 硬冲突数
- 占位模板：[fixtures/golden/_placeholder/](solver/fixtures/golden/_placeholder/README.md)（含 JSON 字段对照详细说明）

**Golden case 文件格式**
每个 case 一个目录，含两个 JSON 文件：

- `input.json` 字段对应 [engine.py](../app/algorithm/engine.py) 中的 dataclass：
  - `courses` → list[`CourseInput`]
  - `classrooms` → list[`ClassroomInput`]，其中 `available_slots` 用 `[[day, slot], ...]` 表示
  - `preferences` → list[`TeacherPreference`]
- `expected.json` 含：
  - `scheduled_count: int` — 期望成功排课数
  - `unscheduled_ids: list[str]` — 期望未能排课的 course_id 集合
  - `max_conflicts: int = 0` — 允许的硬冲突上限
  - `extra: dict` — case 特定断言由 test 函数读取，自由扩展

**添加新用例**
1. 复制 [_placeholder/](solver/fixtures/golden/_placeholder/) 为 `fixtures/golden/<case_name>/`
2. 改写 `input.json` 和 `expected.json`
3. [test_solver_golden.py](solver/test_solver_golden.py) 自动发现并参数化运行，**无需新增测试函数**
4. 如需 case 特定断言（教师工作量上限、跨校区禁忌等），在该文件里另写一个测试函数读 `expected.extra`
5. 跑：`make test-solver`

---

### e2e 层

**负责范围**
API 级端到端测试，纯黑盒视角。和 integration 层共用同一套 [docker-compose.test.yml](../docker-compose.test.yml) 栈，但定位不同——integration 偏跨服务白盒（可读 DB/Redis 验证），e2e 偏用户视角的完整流程。

**框架**
- [e2e/conftest.py](e2e/conftest.py) 提供：
  - `E2E_BASE_URL` — 默认 `http://localhost:8003`，可用环境变量 `E2E_BASE_URL` 覆盖
  - `_require_e2e_stack` — 栈未就绪时整层 skip
  - `admin_client` / `student_client` — 命名空间与 integration 层隔离，互不影响


**添加新用例**
- **冒烟级**（快速验证能跑）：写到 [test_smoke.py](e2e/test_smoke.py)，复用现有双 marker
- **非冒烟 e2e**（异常路径、并发、错误码细分）：另起文件，命名 `test_<场景>.py`，**只用** `pytestmark = pytest.mark.e2e`（不带 smoke），保证冒烟集精简
- 跑：`make test-e2e`（全量 e2e）/ `make test-smoke`（仅冒烟子集）

---

## 给 feature 开发者的快速指引

写 unit 测试时：
1. 文件放 [tests/unit/](unit/) 下，命名 `test_<模块>.py`
2. 加 `pytestmark = pytest.mark.unit` 在文件顶部
3. 复用根 [conftest.py](conftest.py) 的 `client` / `student_client` / `db_session` fixture
4. unit 层不引入真实 MySQL/Redis/Celery
5. 自检：`make test-unit` 跑单元测试

需要构造算法输入时，用 [factories.py](factories.py) 的 `make_course` / `make_classroom` / `make_preference`，**不用手搓 dataclass**。
