"""
app/models/classroom.py
教室数据表模型。
"""

from sqlalchemy import String, Integer, Boolean, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
import enum


class ClassroomType(str, enum.Enum):
    LECTURE       = "LECTURE"       # 普通教室
    LAB_PHYSICS   = "LAB_PHYSICS"   # 物理实验室
    LAB_CHEMISTRY = "LAB_CHEMISTRY" # 化学实验室
    LAB_BIOLOGY   = "LAB_BIOLOGY"   # 生物实验室
    COMPUTER_LAB  = "COMPUTER_LAB"  # 机房
    GYM           = "GYM"           # 体育场馆


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, comment="教室编号，如 307表示3楼7号教室")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="教室名称，自由文本如音乐教一")
    campus: Mapped[str] = mapped_column(String(32), nullable=False, comment="所在校区")
    building: Mapped[str] = mapped_column(String(64), nullable=False, comment="所在楼栋")
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, comment="额定容量（人数）")
    room_type: Mapped[ClassroomType] = mapped_column(
        SAEnum(ClassroomType), nullable=False, default=ClassroomType.LECTURE
    )
    # 教室本身的基础可用时段（与排课结果无关），元素 {"day": 1-7, "slot": 1-12}
    available_time: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否可用")
