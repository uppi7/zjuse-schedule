"""
app/models/teacher_preference.py
教师排课偏好数据表模型。

一行 = 教师对"某门课 / 某种教室 / 某个时段 / 某段周次"的一条偏好。
- 除 teacher_id / semester / is_negative 外，所有字段可空。
- is_negative=True 表示"不希望这样排"。
- 匹配规则与软硬约束权重由排课算法实现，本表不定义。
- 与 schedule_tasks 无外键；preference 是教师持久化设置，跨学期需重建。
"""

from sqlalchemy import (
    String, Integer, Boolean, Index, DateTime, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.classroom import ClassroomType
from app.models.schedule import DayOfWeek, WeekParity


class TeacherPreference(Base):
    __tablename__ = "teacher_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 归属与生效范围
    teacher_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="第一组 teacher_id 字符串"
    )
    semester: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="学期，如 2024-2025-1"
    )

    # 作用课程：None 表示该教师在该学期所有课的通用偏好
    course_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="作用课程；None=通用偏好"
    )

    # 教室粒度（任意组合留空；四个全空=对教室无偏好）
    campus: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="校区，如 玉泉")
    building: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="楼栋，如 教三")
    classroom_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="对应 classrooms.code，非外键（容错：教师可能填不存在或已禁用的 code）",
    )
    room_type: Mapped[ClassroomType | None] = mapped_column(
        SAEnum(ClassroomType), nullable=True, comment="取值见 ClassroomType 枚举"
    )

    # 时段粒度
    day_of_week: Mapped[DayOfWeek | None] = mapped_column(SAEnum(DayOfWeek), nullable=True)
    slot_start: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="起始节次 1-12")
    slot_end: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="结束节次 1-12")

    # 周次粒度
    week_start: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="起始周次 1-16")
    week_end: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="结束周次 1-16")
    week_parity: Mapped[WeekParity | None] = mapped_column(
        SAEnum(WeekParity), nullable=True, comment="ALL / ODD / EVEN"
    )

    # 极性
    is_negative: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True=不希望这样排；False=希望这样排",
    )

    # 时间戳
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_pref_teacher_semester", "teacher_id", "semester"),
    )
