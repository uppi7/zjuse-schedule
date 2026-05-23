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
| campus | VARCHAR(32) | 所在校区，如"玉泉" |
| building | VARCHAR(64) | 所在楼栋 |
| capacity | INT | 额定容量 |
| room_type | ENUM | LECTURE / LAB_PHYSICS / LAB_CHEMISTRY / LAB_BIOLOGY / COMPUTER_LAB / GYM |
| available_time | JSON | 教室基础可用时段数组，元素 `{"day":1-7, "slot":1-12}`；与排课结果无关，表达此教室"原则上可被排课的窗口" |
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
| result_meta | JSON | 任务结果摘要；如 `{"unscheduled":["C017"],"unscheduled_count":1}` |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### `schedule_entries` — 课表条目

> 一行 = 一门课的一个时段（一个教室 × 一个星期几 × 一段连续节次 × 一段周次区间）。
> 同一门课的多个时段写多行（`course_id` 相同）。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | 自增主键 |
| task_id | INT FK | 所属排课任务 |
| semester | VARCHAR(16) | 学期 |
| course_id | VARCHAR(32) | 课程 ID（来自第一组，不建外键） |
| teacher_ids | JSON | 该时段授课教师 ID 数组（合上时多人），元素为字符串 |
| classroom_id | INT FK | 教室 ID（本地） |
| day_of_week | ENUM | 1=周一 … 7=周日 |
| slot_start | INT | 起始节次（1-12） |
| slot_end | INT | 结束节次（1-12） |
| week_start | INT | 起始周次（1-16） |
| week_end | INT | 结束周次（1-16） |
| week_parity | ENUM | ALL / ODD / EVEN ——`ALL`=每周；`ODD`=单周；`EVEN`=双周 |

**周次约定**：一学期固定 16 周，前半学期 = 1-8 周，后半学期 = 9-16 周。半学期课通过 `week_start/week_end` 区间表达；单双周课通过 `week_parity` 在区间内进一步限定。

### `teacher_preferences` — 教师排课偏好

> 一行 = 教师对"某门课 / 某种教室 / 某个时段 / 某段周次"的一条偏好。
> 除 `teacher_id`、`semester`、`is_negative` 外字段全可选。
> `is_negative=True` 表示"不希望这样排"。匹配规则与软硬约束权重由排课算法实现自定，本表不定义。
> 与 `schedule_tasks` 无外键；偏好是教师持久化设置，跨学期需重建。

| 字段 | 类型 | 可空 | 说明 |
|---|---|---|---|
| id | INT PK | 否 | 自增主键 |
| teacher_id | VARCHAR(32) | 否 | 第一组 teacher_id 字符串 |
| semester | VARCHAR(16) | 否 | 学期，如 2024-2025-1 |
| course_id | VARCHAR(32) | 是 | 作用课程；None=该教师在该学期所有课的通用偏好 |
| campus | VARCHAR(32) | 是 | 校区，如 "玉泉" |
| building | VARCHAR(64) | 是 | 楼栋，如 "教三" |
| classroom_code | VARCHAR(32) | 是 | 对应 `classrooms.code`，非外键（容错） |
| room_type | ENUM | 是 | 取值见 `ClassroomType`（LECTURE / LAB_PHYSICS / LAB_CHEMISTRY / LAB_BIOLOGY / COMPUTER_LAB / GYM） |
| day_of_week | ENUM | 是 | 1=周一 … 7=周日 |
| slot_start | INT | 是 | 起始节次 1-12 |
| slot_end | INT | 是 | 结束节次 1-12 |
| week_start | INT | 是 | 起始周次 1-16 |
| week_end | INT | 是 | 结束周次 1-16 |
| week_parity | ENUM | 是 | ALL / ODD / EVEN |
| is_negative | BOOL | 否 | True=不希望这样排；默认 False |
| created_at | DATETIME | 否 | 创建时间 |
| updated_at | DATETIME | 否 | 更新时间 |

**索引**：联合索引 `(teacher_id, semester)`，供按学期批量装配算法输入使用。

**字段组合语义**：
- `course_id` 留空：该偏好作用于该教师在该学期的所有课。
- 教室四个字段（`campus` / `building` / `classroom_code` / `room_type`）可任意组合留空；全空 = 对教室无偏好。
- 教室、时段、周次三组字段全部留空时，该偏好没有实际作用对象，应在 service 层校验拒绝（本期 TODO）。

---

## 二、跨系统数据契约

### 2.1 鉴权约定（子系统间互信）

子系统之间默认互信。调用第一组时，本系统将当前调用者身份透传到下游：

| Header | 值 | 说明 |
|---|---|---|
| `X-User-Id` | 调用者 user_id | 排课任务里 = 触发排课的管理员 id（即 `ScheduleTask.triggered_by`） |
| `X-User-Role` | `ADMIN` / `TEACHER` / `STUDENT` | 调用者角色；排课任务默认 `ADMIN` |

封装位置：`app/core/external_clients.py → InfoServiceClient.__init__(user_id, role)`。

### 2.2 从第一组拉取：课程数据

**接口：** `GET http://info-service:8000/api/v1/courses?semester=2024-2025-1`

**请求 Header：** 见 §2.1 互信约定。

**响应格式（包络 + data 数组）：**

```json
{
  "code": 0,
  "msg": "success",
  "data": [
    {
      "course_id": "C001",
      "name": "高等数学",
      "teacher_id": "T001",
      "semester": "2024-2025-1",
      "student_count": 60,
      "room_requirements": [
        {"room_type": "LECTURE", "hours": 4}
      ]
    }
  ]
}
```

字段约定（排课算法依赖以下字段，第一组必须返回）：

| 字段 | 类型 | 说明 |
|---|---|---|
| course_id | str | 课程唯一标识 |
| name | str | 课程名称 |
| teacher_id | str | 主讲教师 ID；合上课暂按单教师处理 |
| semester | str | 学期标识 |
| student_count | int | 选课人数 |
| room_requirements | list | 每周分房间类型的学时需求。每项 `{"room_type": <ClassroomType 取值>, "hours": int}`，当前枚举：`LECTURE` / `LAB_PHYSICS` / `LAB_CHEMISTRY` / `LAB_BIOLOGY` / `COMPUTER_LAB` / `GYM`（权威定义见 `ClassroomType`）。混合课（如理论课+实验课）使用多项；纯讲授课传单项即可。`hours == 0` 的项应被忽略或上游剔除。 |


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
      "teacher_ids": ["T001", "T002"],
      "classroom_id": 3,
      "day_of_week": 1,
      "slot_start": 1,
      "slot_end": 2,
      "week_start": 1,
      "week_end": 16,
      "week_parity": "ALL"
    }
  ]
}
```

支持的筛选参数：`semester`（必填）、`teacher_id`（可选，匹配 `teacher_ids` 数组中任一成员）、`course_id`（可选）。
