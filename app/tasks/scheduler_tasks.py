"""
app/tasks/scheduler_tasks.py
具体的排课异步任务定义。

模块职责划分：
  - 本文件：编排排课主任务的 4 个步骤、状态汇报、异常处理
  - app/core/external_clients.py：与第一组的 HTTP 契约（输入：semester + 调用者身份；输出：课程 dict 列表）
  - app/algorithm/engine.py：纯算法逻辑（输入：dataclass；输出：ScheduleResult 列表）
"""

import time
import asyncio
from celery import shared_task
from celery.utils.log import get_task_logger

from app.tasks.celery_app import celery_app
from app.algorithm.engine import (
    CourseInput, ClassroomInput, TeacherPreference, ScheduleResult,
)

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    name="scheduler.run_auto_schedule",
    max_retries=2,
    default_retry_delay=30,
)
def run_auto_schedule(self, semester: str, triggered_by: str) -> dict:
    """
    排课主任务。由 FastAPI 接口通过 .delay() 调用，运行在 Celery Worker 进程中。

    执行步骤：
      1. 从第一组拉课程 + 从本地 DB 读教室 → 转换为算法 dataclass
      2. 调用排课算法引擎
      3. 将结果写入 MySQL
      4. 通知下游选课组（拉取模式，仅日志记录）
    """
    logger.info(f"[run_auto_schedule] START semester={semester}, triggered_by={triggered_by}")

    try:
        # ── Step 1: 拉取上游数据 ─────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"progress": 10, "message": "正在从基础信息组拉取数据..."})
        courses, classrooms, preferences = asyncio.run(_fetch_upstream_data(semester, triggered_by))
        logger.info(
            f"Fetched: courses={len(courses)}, classrooms={len(classrooms)}, "
            f"preferences={len(preferences)}"
        )

        # ── Step 2: 运行排课算法 ──────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"progress": 30, "message": "正在运行排课算法..."})
        time.sleep(5)   # 模拟算法耗时；真实算法接入时由 engine.run_schedule 取代
        schedule_results, unscheduled = _build_stub_results(courses), []

        self.update_state(state="PROGRESS", meta={"progress": 70, "message": "算法完成，正在写入数据库..."})

        # ── Step 3: 写入 MySQL ────────────────────────────────────────────
        asyncio.run(_save_results(self.request.id, semester, schedule_results))

        # ── Step 4: 通知下游 ──────────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"progress": 90, "message": "正在通知下游系统..."})
        asyncio.run(_notify_downstream(semester))

        result_summary = {
            "semester": semester,
            "total_courses": len(courses),
            "scheduled": len(schedule_results),
            "unscheduled": [c.course_id for c in unscheduled] if unscheduled else [],
            "unscheduled_count": len(unscheduled),
        }
        logger.info(f"[run_auto_schedule] DONE: {result_summary}")
        return result_summary

    except Exception as exc:
        logger.error(f"[run_auto_schedule] FAILED: {exc}", exc_info=True)
        raise self.retry(exc=exc) if self.request.retries < self.max_retries else exc



async def _fetch_upstream_data(
    semester: str, triggered_by: str
) -> tuple[list[CourseInput], list[ClassroomInput], list[TeacherPreference]]:
    """
    TODO: 把上游数据装配成算法所需的 dataclass。

    输入：
      semester     ── 当前学期，如 "2024-2025-1"
      triggered_by ── 触发排课的管理员 user_id，用于透传到第一组 X-User-Id

    输出：三个列表，按位置返回 (courses, classrooms, preferences)
      courses      ── list[CourseInput]
      classrooms   ── list[ClassroomInput]
      preferences  ── list[TeacherPreference]

    实现要点：
      1) 课程：用 InfoServiceClient(user_id=triggered_by, role="ADMIN") 调
         get_all_courses(semester)；得到的 dict 字段映射到 CourseInput：
             course_id     ← dict["course_id"]
             teacher_ids   ← [dict["teacher_id"]]    # 上游目前单教师，包成一元列表
             student_count ← dict["student_count"]
             weekly_hours  ← dict["weekly_hours"]
             needs_lab     ← dict["needs_lab"]
         记得 try/finally 调 client.aclose()。
      2) 教室：从本地 Classroom 表查 is_active=True 的全部行，映射到 ClassroomInput：
             classroom_id    ← row.id
             campus          ← row.campus
             capacity        ← row.capacity
             is_lab          ← row.room_type == ClassroomType.LAB
             available_slots ← {(d["day"], d["slot"]) for d in row.available_time}
         需用 asyncio 安全的临时 session（参考 app/core/database.py 的 AsyncSessionLocal）。
      3) 教师偏好：调用
             from app.services import teacher_preference_service
             preferences = await teacher_preference_service.list_for_algorithm(db, semester)
         该函数返回 list[engine.TeacherPreference]，直接作为第三返回值。
         无偏好时返回空列表，算法应能容忍。

    错误处理：
      - 上游 4xx/5xx：raise，让 Celery 任务进入 FAILED
      - 本地 DB 无教室：raise ValueError，主任务捕获后 update_state 为 FAILED
    """
    raise NotImplementedError("TODO: 签名与 I/O 契约见 docstring")


async def _save_results(
    task_id: str, semester: str, results: list[ScheduleResult]
) -> None:
    """
    TODO: 将算法输出的 ScheduleResult 列表写入 schedule_entries 表。

    输入：
      task_id  ── 当前 Celery 任务 ID，用来反查 ScheduleTask.id 作为外键
      semester ── 学期标识
      results  ── 算法输出，list[ScheduleResult]（结构见 app/algorithm/engine.py）

    输出：None；副作用是表写入。

    实现要点：
      1) 用 select(ScheduleTask).where(celery_task_id=task_id) 拿到 task 行，取其 id。
      2) 幂等：写入前 DELETE FROM schedule_entries WHERE task_id=<id>（同一任务重跑场景）。
      3) 字段映射 ScheduleResult → ScheduleEntry：
             course_id   ← r.course_id
             teacher_ids ← r.teacher_ids               # JSON 列，直接传 list
             classroom_id ← r.classroom_id
             day_of_week ← DayOfWeek(r.day_of_week)
             slot_start / slot_end / week_start / week_end ← 同名
             week_parity ← WeekParity(r.week_parity)
      4) 更新对应 ScheduleTask.status = ScheduleStatus.SUCCESS（或外层 task 完成时再改）。
      5) DB session 用法参考 _fetch_upstream_data 中的临时 session 模式。
    """
    # 当前为空实现，算法和写库未接入时排课结果不落库。
    pass


async def _notify_downstream(semester: str) -> None:
    """通知下游选课组（拉取模式，仅日志记录，不主动推送）。"""
    from app.services.schedule_service import notify_downstream
    await notify_downstream(semester, [])


def _build_stub_results(courses: list[CourseInput]) -> list[ScheduleResult]:
    """
    临时占位结果生成器；真实算法接入后此函数应删除，
    Step 2 改为调用 app.algorithm.engine.run_schedule(...)。
    """
    return [
        ScheduleResult(
            course_id=c.course_id,
            teacher_ids=list(c.teacher_ids),
            classroom_id=1,
            day_of_week=1,
            slot_start=1,
            slot_end=2,
        )
        for c in courses
    ]
