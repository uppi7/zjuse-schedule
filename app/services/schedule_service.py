"""
app/services/schedule_service.py
排课业务逻辑：触发任务、查询状态、手动调课、交付下游。
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from celery.result import AsyncResult

from app.models.schedule import ScheduleTask, ScheduleEntry, ScheduleStatus
from app.schemas.schedule import (
    AutoScheduleRequest,
    ManualAdjustRequest,
    ScheduleStatusResponse,
    ScheduleEntryOut,
)
from app.schemas.response import BizCode
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": BizCode.TASK_ALREADY_RUNNING, "msg": "A schedule task for this semester is already running"},
        )

    # 推送到 Celery（不阻塞）
    celery_task = scheduler_tasks.run_auto_schedule.delay(req.semester, triggered_by)

    # 记录到 DB
    task_record = ScheduleTask(
        celery_task_id=celery_task.id,
        semester=req.semester,
        status=ScheduleStatus.PENDING,
        triggered_by=triggered_by,
    )
    db.add(task_record)
    await db.commit()

    return celery_task.id, req.semester


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": BizCode.TASK_NOT_FOUND, "msg": f"ScheduleEntry {req.entry_id} not found"},
        )

    for field in ("new_classroom_id", "new_day_of_week", "new_slot_start", "new_slot_end",
                  "new_week_start", "new_week_end"):
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
    """查询课表条目，支持按学期/教师/课程筛选。"""
    stmt = select(ScheduleEntry).where(ScheduleEntry.semester == semester)
    if teacher_id:
        stmt = stmt.where(ScheduleEntry.teacher_id == teacher_id)
    if course_id:
        stmt = stmt.where(ScheduleEntry.course_id == course_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def notify_downstream(semester: str, entries: list[ScheduleEntry]) -> None:
    """
    通知下游子系统（智能选课组）排课结果已就绪。

    TODO: [外部规范协商] 与第三组(智能选课组)确认通知方式：
      方案A：通过 MQ（Redis Pub/Sub 或 Kafka）发送事件广播
        - 事件格式：{"event": "schedule_ready", "semester": "...", "entry_count": N}
      方案B：提供批量拉取 API，选课组自行 GET /api/v1/schedule/entries?semester=...
        - 当前框架已实现此 API，选课组可直接调用

    当前为占位实现，仅打印日志。
    """
    print(
        f"[notify_downstream] Semester {semester} schedule ready, "
        f"{len(entries)} entries. TODO: 与第三组确认通知方式后实现。"
    )
