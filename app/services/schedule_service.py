"""
app/services/schedule_service.py
排课业务逻辑：触发任务、查询状态、手动调课、交付下游。
"""

from uuid import uuid4

from celery.result import AsyncResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import ScheduleTask, ScheduleEntry, ScheduleStatus
from app.schemas.schedule import (
    AutoScheduleRequest,
    ManualAdjustRequest,
    ScheduleStatusResponse,
    ScheduleEntryOut,
)
from app.schemas.response import BizCode, BizException
from app.tasks.celery_app import celery_app
from app.tasks import scheduler_tasks


async def trigger_auto_schedule(
    db: AsyncSession,
    req: AutoScheduleRequest,
    triggered_by: str,
) -> tuple[str, str]:
    """
    触发排课任务（异步，非阻塞）。
    返回 (celery_task_id, semester)。
    """
    # 防止重复触发同一学期
    running = await db.scalar(
        select(ScheduleTask).where(
            ScheduleTask.semester == req.semester,
            ScheduleTask.status.in_([ScheduleStatus.PENDING, ScheduleStatus.RUNNING]),
        )
    )
    if running:
        raise BizException(
            BizCode.TASK_ALREADY_RUNNING,
            "A schedule task for this semester is already running",
        )

    celery_task_id = str(uuid4())
    task_record = ScheduleTask(
        celery_task_id=celery_task_id,
        semester=req.semester,
        status=ScheduleStatus.PENDING,
        triggered_by=triggered_by,
    )
    db.add(task_record)
    await db.commit()

    try:
        scheduler_tasks.run_auto_schedule.apply_async(
            args=(req.semester, triggered_by),
            task_id=celery_task_id,
        )
    except Exception as exc:
        task_record.status = ScheduleStatus.FAILED
        task_record.error_msg = str(exc)
        await db.commit()
        raise

    return celery_task_id, req.semester


def get_schedule_status(task_id: str) -> ScheduleStatusResponse:
    """
    从 Celery/Redis 查询任务状态（无需数据库）。
    """
    result = AsyncResult(task_id, app=celery_app)

    state_map = {
        "PENDING": ScheduleStatus.PENDING,
        "STARTED": ScheduleStatus.RUNNING,
        "PROGRESS": ScheduleStatus.RUNNING,
        "SUCCESS": ScheduleStatus.SUCCESS,
        "FAILURE": ScheduleStatus.FAILED,
    }
    status_val = state_map.get(result.state, ScheduleStatus.RUNNING)

    progress = 0
    message = ""
    result_summary = None

    if result.state == "PROGRESS" and isinstance(result.info, dict):
        progress = result.info.get("progress", 0)
        message = result.info.get("message", "")
    elif result.state == "SUCCESS":
        progress = 100
        result_summary = result.result
    elif result.state == "FAILURE":
        message = str(result.info)

    return ScheduleStatusResponse(
        task_id=task_id,
        status=status_val,
        progress=progress,
        message=message,
        result_summary=result_summary,
    )


async def manual_adjust(
    db: AsyncSession,
    req: ManualAdjustRequest,
) -> ScheduleEntry:
    """手动调课：修改单条 ScheduleEntry。"""
    entry = await db.get(ScheduleEntry, req.entry_id)
    if not entry:
        raise BizException(
            BizCode.TASK_NOT_FOUND,
            f"ScheduleEntry {req.entry_id} not found",
        )

    for field in ("new_teacher_ids", "new_classroom_id", "new_day_of_week",
                  "new_slot_start", "new_slot_end",
                  "new_week_start", "new_week_end", "new_week_parity"):
        value = getattr(req, field)
        if value is not None:
            attr = field.removeprefix("new_")
            setattr(entry, attr, value)

    await db.commit()
    await db.refresh(entry)
    return entry


async def get_schedule_entries(
    db: AsyncSession,
    semester: str,
    teacher_id: str | None = None,
    course_id: str | None = None,
) -> list[ScheduleEntry]:
    """
    查询课表条目，支持按学期/教师/课程筛选。
    teacher_id 是 JSON 数组的成员匹配，跨 MySQL/SQLite 兼容地在 Python 侧过滤。
    """
    stmt = select(ScheduleEntry).where(ScheduleEntry.semester == semester)
    if course_id:
        stmt = stmt.where(ScheduleEntry.course_id == course_id)
    result = await db.execute(stmt)
    entries = list(result.scalars().all())
    if teacher_id:
        entries = [e for e in entries if teacher_id in (e.teacher_ids or [])]
    return entries


async def get_teacher_timetable(
    db: AsyncSession,
    teacher_id: str,
    semester: str,
    week: int | None = None,
) -> list[ScheduleEntry]:
    """
    查询某教师在某学期的课表，可按 week 切片。

    week 切片规则：
      - entry.week_start <= week <= entry.week_end
      - 且 entry.week_parity 满足：ALL=任意 / ODD=week 为奇数 / EVEN=week 为偶数
    """
    # TODO: 实现按 teacher_id + semester + 可选 week 的查询。
    # 可复用 get_schedule_entries(db, semester, teacher_id=teacher_id) 的过滤逻辑，
    # 再在 Python 侧按 week 与 week_parity 过滤
    raise NotImplementedError("get_teacher_timetable: pending implementation")


async def notify_downstream(semester: str, entries: list[ScheduleEntry]) -> None:
    """
    排课完成后的下游通知。

    交付方式：拉取 API。
    选课组（第三组）通过 GET /api/v1/schedule/entries?semester=<semester> 主动拉取，
    本系统无需主动推送。
    """
    import logging
    logging.getLogger(__name__).info(
        "Schedule ready: semester=%s, entries=%d. "
        "Downstream can pull via GET /api/v1/schedule/entries?semester=%s",
        semester, len(entries), semester,
    )
