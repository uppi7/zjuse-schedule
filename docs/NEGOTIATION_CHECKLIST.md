# 跨组协商结论记录 — 自动排课组

> 本文档记录已落定的跨组约定。若后续协商结果有变，直接修改对应行并更新代码。

---

## 议题一：与第一组（基础信息组）

### 1-A 上游 API 地址与路径 ✅ 已落定

| 编号 | 事项 | 确认值 | 配置位置 |
|---|---|---|---|
| 1-A-1 | 基础信息服务内网地址 | `http://info-service:8000` | `.env` → `INFO_SERVICE_BASE_URL` |
| 1-A-2 | 教师列表 API 路径 | `GET /api/v1/teachers` | `.env` → `INFO_SERVICE_TEACHERS_PATH` |
| 1-A-3 | 课程列表 API 路径 | `GET /api/v1/courses` | `.env` → `INFO_SERVICE_COURSES_PATH` |

### 1-B 上游 API 返回的 JSON 结构 ✅ 已落定

响应外层格式与本系统一致：`{"code": 0, "msg": "success", "data": [...]}`

**教师接口**每条记录字段：

| 字段名 | 类型 | 说明 |
|---|---|---|
| `teacher_id` | string | 教师唯一标识 |
| `name` | string | 姓名 |

**课程接口**每条记录字段：

| 字段名 | 类型 | 说明 |
|---|---|---|
| `course_id` | string | 课程唯一标识 |
| `name` | string | 课程名称 |
| `teacher_id` | string | 授课教师 ID |
| `weekly_hours` | int | 每周课时数 |
| `student_count` | int | 选课学生人数 |
| `needs_lab` | bool | 是否需要实验室，默认 false |

> 代码位置：`app/core/external_clients.py`

### 1-C 网关认证透传规范 ✅ 已落定

| 事项 | 确认值 | 配置位置 |
|---|---|---|
| 用户 ID Header | `X-User-Id` | `.env` → `AUTH_HEADER_USER_ID` |
| 用户角色 Header | `X-User-Role` | `.env` → `AUTH_HEADER_USER_ROLE` |
| 教务管理员 Role Code | `ADMIN` | `.env` → `ROLE_ADMIN` |
| 教师 Role Code | `TEACHER` | `.env` → `ROLE_TEACHER` |
| 学生 Role Code | `STUDENT` | `.env` → `ROLE_STUDENT` |

---

## 议题二：与第三组（智能选课组）

### 2-A 排课结果交付方式 ✅ 已落定：拉取 API

选课组通过以下接口主动拉取课表，排课组无需主动推送：

```
GET /api/v1/schedule/entries?semester=2024-2025-1
```

返回字段：`id, semester, course_id, teacher_id, classroom_id, day_of_week, slot_start, slot_end, week_start, week_end`

若后续需要增加字段，修改 `app/schemas/schedule.py` 中的 `ScheduleEntryOut`。

---

## 议题三：与大组

### 3-A 业务错误码号段 ✅ 已落定

排课组占用 **2000–2099**，见 `app/schemas/response.py` → `BizCode`。

### 3-B 基础设施资源分配 ✅ 已落定

| 资源 | 分配值 | 配置位置 |
|---|---|---|
| Redis DB（Celery broker） | DB 2 | `.env` → `CELERY_BROKER_DB` |
| Redis DB（Celery result） | DB 3 | `.env` → `CELERY_RESULT_DB` |
| MySQL 内网服务别名 | `mysql` | `.env` → `MYSQL_HOST` |
| Redis 内网服务别名 | `redis` | `.env` → `REDIS_HOST` |

### 3-C 网络与端口 ✅ 已落定

| 事项 | 值 | 配置位置 |
|---|---|---|
| API 宿主机端口 | `8002` | `docker-compose.yml` |
| Docker 网络名 | `app-network` | `docker-compose.yml` |
