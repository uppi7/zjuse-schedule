"""
app/api/v1/schedule.py
排课触发、状态查询、手动调课、课表查询接口。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.dependencies import get_current_user, require_admin, require_teacher_or_admin
from app.core.security import CurrentUser
from app.schemas.schedule import (
    AutoScheduleRequest,
    AutoScheduleResponse,
    ScheduleStatusResponse,
    ManualAdjustRequest,
    ScheduleEntryOut,
)
from app.schemas.response import ApiResponse
from app.services import schedule_service

router = APIRouter(prefix="/schedule", tags=["排课管理"])


@router.post(
    "/auto-schedule",
    response_model=ApiResponse[AutoScheduleResponse],
    status_code=202,
    summary="触发自动排课（异步）",
)
async def trigger_auto_schedule(
    req: AutoScheduleRequest,
    db: AsyncSession = Depends(get_db),
    admin: CurrentUser = Depends(require_admin),
):
    """
    触发排课任务，立即返回 task_id。
    排课是耗时 CPU 密集型操作，由 Celery Worker 异步执行，接口不阻塞。
    """
    task_id, semester = await schedule_service.trigger_auto_schedule(db, req, admin.user_id)
    return ApiResponse.ok(
        data=AutoScheduleResponse(task_id=task_id, semester=semester),
        msg="Schedule task submitted",
    )


@router.get(
    "/schedule-status/{task_id}",
    response_model=ApiResponse[ScheduleStatusResponse],
    summary="查询排课任务进度",
)
def get_schedule_status(
    task_id: str,
    _user: CurrentUser = Depends(get_current_user),
):
    """
    通过 task_id 轮询排课进度（0-100%）和最终结果。
    状态存储在 Redis，无需查询 MySQL。
    """
    data = schedule_service.get_schedule_status(task_id)
    return ApiResponse.ok(data=data)


@router.post(
    "/manual-adjust",
    response_model=ApiResponse[ScheduleEntryOut],
    summary="手动调课",
)
async def manual_adjust(
    req: ManualAdjustRequest,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """
    对已生成的课表进行手动调整（换教室、换时间段等）。
    仅管理员可操作。
    """
    entry = await schedule_service.manual_adjust(db, req)
    return ApiResponse.ok(data=ScheduleEntryOut.model_validate(entry))


@router.get(
    "/entries",
    response_model=ApiResponse[list[ScheduleEntryOut]],
    summary="查询课表条目",
)
async def get_schedule_entries(
    semester: str = Query(..., description="学期，如 2024-2025-1"),
    teacher_id: str | None = Query(default=None),
    course_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    """
    查询排课结果。支持按学期、教师、课程筛选。
    下游子系统（智能选课组）可通过此接口拉取课表数据。
    """
    entries = await schedule_service.get_schedule_entries(
        db, semester, teacher_id=teacher_id, course_id=course_id
    )
    return ApiResponse.ok(data=[ScheduleEntryOut.model_validate(e) for e in entries])
