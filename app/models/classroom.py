"""
app/models/classroom.py
教室数据表模型。
"""

from sqlalchemy import String, Integer, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
import enum


class ClassroomType(str, enum.Enum):
    LECTURE = "LECTURE"       # 普通教室
    LAB = "LAB"               # 实验室
    GYM = "GYM"               # 体育场馆
    MULTIMEDIA = "MULTIMEDIA"  # 多媒体教室


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, comment="教室编号，如 A101")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="教室名称")
    building: Mapped[str] = mapped_column(String(64), nullable=False, comment="所在楼栋")
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, comment="额定容量（人数）")
    room_type: Mapped[ClassroomType] = mapped_column(
        SAEnum(ClassroomType), nullable=False, default=ClassroomType.LECTURE
    )
    has_projector: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ac: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否有空调")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否可用")
