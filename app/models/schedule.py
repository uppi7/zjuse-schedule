"""
app/models/schedule.py
排课结果与排课任务数据表模型。
"""

from sqlalchemy import String, Integer, ForeignKey, Text, JSON, Enum as SAEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class ScheduleStatus(str, enum.Enum):
    PENDING = "PENDING"       # 等待执行
    RUNNING = "RUNNING"       # 算法运行中
    SUCCESS = "SUCCESS"       # 排课成功
    FAILED = "FAILED"         # 排课失败
    PARTIAL = "PARTIAL"       # 部分成功（有未排课课程）


class DayOfWeek(int, enum.Enum):
    MON = 1
    TUE = 2
    WED = 3
    THU = 4
    FRI = 5
    SAT = 6
    SUN = 7


class WeekParity(str, enum.Enum):
    ALL = "ALL"       # 每周都上
    ODD = "ODD"       # 单周
    EVEN = "EVEN"     # 双周


class ScheduleTask(Base):
    """记录每次排课任务的元信息与 Celery task_id。"""
    __tablename__ = "schedule_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    celery_task_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    semester: Mapped[str] = mapped_column(String(16), nullable=False, comment="学期，如 2024-2025-1")
    status: Mapped[ScheduleStatus] = mapped_column(
        SAEnum(ScheduleStatus), nullable=False, default=ScheduleStatus.PENDING
    )
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False, comment="触发人 user_id")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 一次排课任务产生多条课表记录
    schedule_entries: Mapped[list["ScheduleEntry"]] = relationship(back_populates="task")


class ScheduleEntry(Base):
    """
    最终排课结果：一行 = 一门课的一个时段（一个教室、一个星期几、一段连续节次、一段周次区间）。
    同一门课的多个时段 → 多行（course_id 相同）。
    """
    __tablename__ = "schedule_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("schedule_tasks.id"), nullable=False)
    semester: Mapped[str] = mapped_column(String(16), nullable=False)

    # 来自基础信息组（外键不在本库，用普通字段存 ID）
    course_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="课程 ID（来自第一组）")
    # 该时段授课的教师 ID 列表（合上课时多人，元素为第一组的 teacher_id 字符串）
    teacher_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"), nullable=False)
    day_of_week: Mapped[DayOfWeek] = mapped_column(SAEnum(DayOfWeek), nullable=False)
    slot_start: Mapped[int] = mapped_column(Integer, nullable=False, comment="起始节次，1-12")
    slot_end: Mapped[int] = mapped_column(Integer, nullable=False, comment="结束节次，1-12")
    week_start: Mapped[int] = mapped_column(Integer, nullable=False, comment="起始周次，1-16")
    week_end: Mapped[int] = mapped_column(Integer, nullable=False, comment="结束周次，1-16")
    # 周次奇偶：ALL=每周；ODD=单周；EVEN=双周。半学期用 week_start/end 区间表达（1-8 或 9-16）
    week_parity: Mapped[WeekParity] = mapped_column(
        SAEnum(WeekParity), nullable=False, default=WeekParity.ALL
    )

    task: Mapped["ScheduleTask"] = relationship(back_populates="schedule_entries")
