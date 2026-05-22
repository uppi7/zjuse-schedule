"""
app/tasks/scheduler_tasks.py
具体的排课异步任务定义。

模块职责划分：
  - 本文件：编排排课主任务的 4 个步骤、状态汇报、异常处理
  - app/core/external_clients.py：与第一组的 HTTP 契约（输入：semester + 调用者身份；输出：课程 dict 列表）
  - app/algorithm/engine.py：纯算法逻辑（输入：dataclass；输出：ScheduleResult 列表）
"""

import asyncio

from celery.utils.log import get_task_logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine as db_engine
from app.core.external_clients import InfoServiceClient
from app.models.classroom import Classroom
from app.models.schedule import (
    DayOfWeek,
    ScheduleEntry,
    ScheduleStatus,
    ScheduleTask,
    WeekParity,
)
from app.schemas.response import BizCode, BizException
from app.services import teacher_preference_service
from app.algorithm.engine import (
    CourseInput, ClassroomInput, TeacherPreference, ScheduleResult,
    RoomRequirement, RoomType, run_schedule,
)
from app.tasks.celery_app import celery_app

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
        result_summary = asyncio.run(_run_auto_schedule_async(self, semester, triggered_by))
        logger.info(f"[run_auto_schedule] DONE: {result_summary}")
        return result_summary

    except Exception as exc:
        logger.error(f"[run_auto_schedule] FAILED: {exc}", exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        asyncio.run(_mark_task_failed_and_dispose(self.request.id, exc))
        raise exc


async def _run_auto_schedule_async(self, semester: str, triggered_by: str) -> dict:
    try:
        await _mark_task_running(self.request.id)

        # ── Step 1: 拉取上游数据 ─────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"progress": 10, "message": "正在从基础信息组拉取数据..."})
        courses, classrooms, preferences = await _fetch_upstream_data(semester, triggered_by)
        logger.info(
            f"Fetched: courses={len(courses)}, classrooms={len(classrooms)}, "
            f"preferences={len(preferences)}"
        )

        # ── Step 2: 运行排课算法 ──────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"progress": 30, "message": "正在运行排课算法..."})
        schedule_results, unscheduled = run_schedule(courses, classrooms, preferences)
        unscheduled = _normalize_unscheduled(unscheduled)
        if unscheduled and not schedule_results:
            raise BizException(
                BizCode.ALGORITHM_NO_SOLUTION,
                "No feasible schedule found for any course",
                data={"unscheduled": unscheduled},
            )

        self.update_state(state="PROGRESS", meta={"progress": 70, "message": "算法完成，正在写入数据库..."})

        # ── Step 3: 写入 MySQL ────────────────────────────────────────────
        await _save_results(self.request.id, semester, schedule_results, unscheduled)

        # ── Step 4: 通知下游 ──────────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"progress": 90, "message": "正在通知下游系统..."})
        await _notify_downstream(semester)

        return {
            "semester": semester,
            "total_courses": len(courses),
            "scheduled": len(schedule_results),
            "unscheduled": unscheduled,
            "unscheduled_count": len(unscheduled),
        }
    finally:
        await db_engine.dispose()



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
             course_id         ← dict["course_id"]
             teacher_ids       ← [dict["teacher_id"]]    # 上游目前单教师，包成一元列表
             student_count     ← dict["student_count"]
             room_requirements ← [RoomRequirement(RoomType(item["room_type"]), item["hours"])
                                  for item in dict["room_requirements"]]
         记得 try/finally 调 client.aclose()。
      2) 教室：从本地 Classroom 表查 is_active=True 的全部行，映射到 ClassroomInput：
             classroom_id    ← row.id
             campus          ← row.campus
             capacity        ← row.capacity
             room_type       ← RoomType(row.room_type.value)    # DB ClassroomType → 算法 RoomType
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
    raw_courses = await _fetch_course_payloads(semester, triggered_by)
    courses = _map_courses(raw_courses)

    async with AsyncSessionLocal() as db:
        classroom_rows = (
            await db.execute(
                select(Classroom)
                .where(Classroom.is_active.is_(True))
                .order_by(Classroom.id.asc())
            )
        ).scalars().all()
        classrooms = [_map_classroom(row) for row in classroom_rows]
        if not classrooms:
            raise ValueError("No active classrooms available for scheduling")

        preferences = await teacher_preference_service.list_for_algorithm(db, semester)

    return courses, classrooms, preferences


async def _save_results(
    task_id: str,
    semester: str,
    results: list[ScheduleResult],
    unscheduled: list[str],
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
    async with AsyncSessionLocal() as db:
        async with db.begin():
            task = await _get_schedule_task(db, task_id)
            await db.execute(delete(ScheduleEntry).where(ScheduleEntry.task_id == task.id))

            entries = [
                ScheduleEntry(
                    task_id=task.id,
                    semester=semester,
                    course_id=result.course_id,
                    teacher_ids=list(result.teacher_ids),
                    classroom_id=result.classroom_id,
                    day_of_week=DayOfWeek(result.day_of_week),
                    slot_start=result.slot_start,
                    slot_end=result.slot_end,
                    week_start=result.week_start,
                    week_end=result.week_end,
                    week_parity=WeekParity(result.week_parity),
                )
                for result in results
            ]
            db.add_all(entries)

            task.status = ScheduleStatus.PARTIAL if unscheduled else ScheduleStatus.SUCCESS
            task.error_msg = None
            task.result_meta = {
                "unscheduled": list(unscheduled),
                "unscheduled_count": len(unscheduled),
            }


async def _notify_downstream(semester: str) -> None:
    """通知下游选课组（拉取模式，仅日志记录，不主动推送）。"""
    from app.services.schedule_service import notify_downstream
    await notify_downstream(semester, [])


async def _fetch_course_payloads(semester: str, triggered_by: str) -> list[dict]:
    client = InfoServiceClient(user_id=triggered_by, role=settings.ROLE_ADMIN)
    try:
        return await client.get_all_courses(semester)
    except Exception as exc:
        if settings.ALLOW_UPSTREAM_STUB_FALLBACK:
            logger.warning(
                "Info service unavailable, using local course stub: semester=%s error=%s",
                semester,
                exc,
            )
            return _build_stub_course_payloads(semester)
        raise BizException(
            BizCode.UPSTREAM_FETCH_FAILED,
            f"Failed to fetch upstream course data: {exc}",
        ) from exc
    finally:
        await client.aclose()


def _map_courses(rows: list[dict]) -> list[CourseInput]:
    try:
        return [_map_course(row) for row in rows]
    except (KeyError, TypeError, ValueError) as exc:
        raise BizException(
            BizCode.UPSTREAM_FETCH_FAILED,
            f"Invalid upstream course payload: {exc}",
        ) from exc


def _map_course(row: dict) -> CourseInput:
    requirements = []
    for item in row["room_requirements"]:
        hours = int(item["hours"])
        if hours <= 0:
            continue
        requirements.append(
            RoomRequirement(
                room_type=RoomType(item["room_type"]),
                hours=hours,
            )
        )

    return CourseInput(
        course_id=str(row["course_id"]),
        teacher_ids=[str(row["teacher_id"])],
        student_count=int(row["student_count"]),
        room_requirements=requirements,
    )


def _map_classroom(row: Classroom) -> ClassroomInput:
    return ClassroomInput(
        classroom_id=row.id,
        campus=row.campus,
        capacity=row.capacity,
        room_type=RoomType(row.room_type.value),
        available_slots={
            (int(item["day"]), int(item["slot"]))
            for item in (row.available_time or [])
        },
    )


def _build_stub_course_payloads(semester: str) -> list[dict]:
    return [
        {
            "course_id": "STUB-C001",
            "name": "Stub Lecture Course",
            "teacher_id": "STUB-T001",
            "semester": semester,
            "student_count": 30,
            "room_requirements": [
                {"room_type": RoomType.LECTURE.value, "hours": 2},
            ],
        }
    ]


def _normalize_unscheduled(unscheduled: list) -> list[str]:
    return [
        str(getattr(item, "course_id", item))
        for item in unscheduled
    ]


async def _mark_task_running(task_id: str) -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            task = await _get_schedule_task(db, task_id)
            task.status = ScheduleStatus.RUNNING
            task.error_msg = None
            task.result_meta = None


async def _mark_task_failed(task_id: str, exc: Exception) -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            task = await _get_schedule_task(db, task_id)
            task.status = ScheduleStatus.FAILED
            task.error_msg = _format_task_error(exc)


async def _mark_task_failed_and_dispose(task_id: str, exc: Exception) -> None:
    try:
        await _mark_task_failed(task_id, exc)
    finally:
        await db_engine.dispose()


async def _get_schedule_task(db: AsyncSession, task_id: str) -> ScheduleTask:
    task = await db.scalar(
        select(ScheduleTask).where(ScheduleTask.celery_task_id == task_id)
    )
    if not task:
        raise BizException(
            BizCode.TASK_NOT_FOUND,
            f"ScheduleTask for celery task {task_id} not found",
        )
    return task


def _format_task_error(exc: Exception) -> str:
    if isinstance(exc, BizException):
        return f"{exc.code}: {exc.msg}"
    return str(exc)
