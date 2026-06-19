"""
app/schemas/schedule.py
排课相关 Pydantic DTO。
"""

from pydantic import BaseModel, Field
from app.models.schedule import ScheduleStatus, DayOfWeek, WeekParity


# ── 触发排课 ──────────────────────────────────────────────────────────────

class AutoScheduleRequest(BaseModel):
    semester: str = Field(..., examples=["2024-2025-1"], description="学期标识，格式：YYYY-YYYY-N")


class AutoScheduleResponse(BaseModel):
    task_id: str = Field(..., description="Celery 任务 ID，用于后续查询进度")
    semester: str


# ── 查询排课状态 ──────────────────────────────────────────────────────────

class ScheduleStatusResponse(BaseModel):
    task_id: str
    status: ScheduleStatus
    progress: int = Field(..., ge=0, le=100, description="进度百分比 0-100")
    message: str = ""
    result_summary: dict | None = None  # 成功时携带摘要数据


# ── 手动调课 ──────────────────────────────────────────────────────────────

class ManualAdjustRequest(BaseModel):
    entry_id: int = Field(..., description="ScheduleEntry 的 ID")
    new_teacher_ids: list[str] | None = None
    new_classroom_id: int | None = None
    new_day_of_week: DayOfWeek | None = None
    new_slot_start: int | None = Field(default=None, ge=1, le=12)
    new_slot_end: int | None = Field(default=None, ge=1, le=12)
    new_week_start: int | None = Field(default=None, ge=1, le=16)
    new_week_end: int | None = Field(default=None, ge=1, le=16)
    new_week_parity: WeekParity | None = None


# ── 课表条目输出 ───────────────────────────────────────────────────────────

class ScheduleEntryOut(BaseModel):
    id: int
    semester: str
    offering_id: str
    course_id: str
    course_code: str | None = None
    course_name: str | None = None
    teacher_ids: list[str]
    classroom_id: int
    day_of_week: DayOfWeek
    slot_start: int
    slot_end: int
    week_start: int
    week_end: int
    week_parity: WeekParity

    model_config = {"from_attributes": True}


# ── 教师课表查询 ───────────────────────────────────────────────────────────

class TeacherTimetableOut(BaseModel):
    teacher_id: str
    semester: str
    week: int | None = None
    entries: list[ScheduleEntryOut]
