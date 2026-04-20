# 数据结构说明

本文档说明本子系统的数据库表结构、Pydantic DTO 以及跨系统数据契约。

---

## 一、数据库表

### `classrooms` — 教室

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | 自增主键 |
| code | VARCHAR(32) UNIQUE | 教室编号，如 A101 |
| name | VARCHAR(64) | 教室名称 |
| building | VARCHAR(64) | 所在楼栋 |
| capacity | INT | 额定容量 |
| room_type | ENUM | LECTURE / LAB / GYM / MULTIMEDIA |
| has_projector | BOOL | 是否有投影仪 |
| has_ac | BOOL | 是否有空调 |
| is_active | BOOL | 是否可用 |

### `schedule_tasks` — 排课任务

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | 自增主键 |
| celery_task_id | VARCHAR(64) UNIQUE | Celery 任务 ID（用于查询 Redis 状态） |
| semester | VARCHAR(16) | 学期，如 2024-2025-1 |
| status | ENUM | PENDING / RUNNING / SUCCESS / FAILED / PARTIAL |
| triggered_by | VARCHAR(32) | 触发人 user_id |
| error_msg | TEXT | 失败时的错误信息 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### `schedule_entries` — 课表条目

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | 自增主键 |
| task_id | INT FK | 所属排课任务 |
| semester | VARCHAR(16) | 学期 |
| course_id | VARCHAR(32) | 课程 ID（来自第一组，不建外键） |
| teacher_id | VARCHAR(32) | 教师 ID（来自第一组，不建外键） |
| classroom_id | INT FK | 教室 ID（本地） |
| day_of_week | ENUM | 1=周一 … 7=周日 |
| slot_start | INT | 起始节次（1-12） |
| slot_end | INT | 结束节次 |
| week_start | INT | 起始周次 |
| week_end | INT | 结束周次 |

---

## 二、跨系统数据契约

### 2.1 从第一组拉取：教师数据

**接口：** `GET http://info-service:8000/api/v1/teachers`

**约定返回格式：**

```json
{
  "code": 0,
  "msg": "success",
  "data": [
    {
      "teacher_id": "T001",
      "name": "张三"
    }
  ]
}
```

解包逻辑见 `app/core/external_clients.py` → `get_all_teachers()`，取 `body["data"]`。

### 2.2 从第一组拉取：课程数据

**接口：** `GET http://info-service:8000/api/v1/courses`

**约定返回格式：**

```json
{
  "code": 0,
  "msg": "success",
  "data": [
    {
      "course_id": "C001",
      "name": "高等数学",
      "teacher_id": "T001",
      "weekly_hours": 4,
      "student_count": 60,
      "needs_lab": false
    }
  ]
}
```

解包逻辑见 `app/core/external_clients.py` → `get_all_courses()`，取 `body["data"]`。

### 2.3 向第三组提供：课表数据

**接口：** `GET /api/v1/schedule/entries?semester=2024-2025-1`

第三组（智能选课组）通过此接口主动拉取课表，排课完成后无需通知，第三组自行轮询或在需要时调用。

**返回格式：**

```json
{
  "code": 0,
  "msg": "success",
  "data": [
    {
      "id": 1,
      "semester": "2024-2025-1",
      "course_id": "C001",
      "teacher_id": "T001",
      "classroom_id": 3,
      "day_of_week": 1,
      "slot_start": 1,
      "slot_end": 2,
      "week_start": 1,
      "week_end": 20
    }
  ]
}
```

支持的筛选参数：`semester`（必填）、`teacher_id`（可选）、`course_id`（可选）。
