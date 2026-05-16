"""
app/schemas/teacher_preference.py
教师排课偏好的 Pydantic DTO。

设计要点：
- Create 不含 teacher_id：教师自助提交，teacher_id 由路由层从 X-User-Id 注入。
- Update 为 PATCH 风格，所有字段可选（含 semester）。
- Out 含 id / teacher_id / 时间戳 / is_negative 等全部字段。
"""

from datetime import datetime
from pydantic import BaseModel, Field, model_validator

from app.models.classroom import ClassroomType
from app.models.schedule import DayOfWeek, WeekParity


# ── 用于 Create 校验的"业务字段"白名单 ───────────────────────────────────────
_BUSINESS_FIELDS = (
    "course_id",
    "campus", "building", "classroom_code", "room_type",
    "day_of_week", "slot_start", "slot_end",
    "week_start", "week_end", "week_parity",
)


class TeacherPreferenceCreate(BaseModel):
    """教师创建一条偏好。teacher_id 不在 body 中，由路由从 X-User-Id 注入。"""

    semester: str = Field(..., max_length=16, examples=["2024-2025-1"])

    course_id: str | None = Field(default=None, max_length=32,
                                  description="None=该教师在该学期所有课的通用偏好")

    campus: str | None = Field(default=None, max_length=32, examples=["玉泉"])
    building: str | None = Field(default=None, max_length=64, examples=["教三"])
    classroom_code: str | None = Field(default=None, max_length=32, examples=["307"])
    room_type: ClassroomType | None = None

    day_of_week: DayOfWeek | None = None
    slot_start: int | None = Field(default=None, ge=1, le=12)
    slot_end: int | None = Field(default=None, ge=1, le=12)

    week_start: int | None = Field(default=None, ge=1, le=16)
    week_end: int | None = Field(default=None, ge=1, le=16)
    week_parity: WeekParity | None = None

    is_negative: bool = Field(default=False, description="True=不希望这样排")

    @model_validator(mode="after")
    def _validate_at_least_one_business_field(self):
        # TODO: 业务约束——至少一个业务字段非空，否则该偏好没有任何作用对象。
        # 目前先放过空载偏好，待产品确认是否强制后再开启。
        # has_any = any(getattr(self, f) is not None for f in _BUSINESS_FIELDS)
        # if not has_any:
        #     raise ValueError("at least one business field must be provided")
        return self


class TeacherPreferenceUpdate(BaseModel):
    """PATCH 风格半字段更新。所有字段（含 semester）皆可选。"""

    semester: str | None = Field(default=None, max_length=16)

    course_id: str | None = Field(default=None, max_length=32)

    campus: str | None = Field(default=None, max_length=32)
    building: str | None = Field(default=None, max_length=64)
    classroom_code: str | None = Field(default=None, max_length=32)
    room_type: ClassroomType | None = None

    day_of_week: DayOfWeek | None = None
    slot_start: int | None = Field(default=None, ge=1, le=12)
    slot_end: int | None = Field(default=None, ge=1, le=12)

    week_start: int | None = Field(default=None, ge=1, le=16)
    week_end: int | None = Field(default=None, ge=1, le=16)
    week_parity: WeekParity | None = None

    is_negative: bool | None = None


class TeacherPreferenceOut(BaseModel):
    id: int
    teacher_id: str
    semester: str

    course_id: str | None
    campus: str | None
    building: str | None
    classroom_code: str | None
    room_type: ClassroomType | None

    day_of_week: DayOfWeek | None
    slot_start: int | None
    slot_end: int | None

    week_start: int | None
    week_end: int | None
    week_parity: WeekParity | None

    is_negative: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
