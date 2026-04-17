"""
app/schemas/classroom.py
教室资源的 Pydantic DTO（Data Transfer Object）。
"""

from pydantic import BaseModel, Field
from app.models.classroom import ClassroomType


class ClassroomCreate(BaseModel):
    code: str = Field(..., max_length=32, examples=["A101"])
    name: str = Field(..., max_length=64, examples=["A座101教室"])
    building: str = Field(..., max_length=64, examples=["A座"])
    capacity: int = Field(..., gt=0, examples=[120])
    room_type: ClassroomType = ClassroomType.LECTURE
    has_projector: bool = False
    has_ac: bool = False


class ClassroomUpdate(BaseModel):
    name: str | None = None
    capacity: int | None = Field(default=None, gt=0)
    room_type: ClassroomType | None = None
    has_projector: bool | None = None
    has_ac: bool | None = None
    is_active: bool | None = None


class ClassroomOut(BaseModel):
    id: int
    code: str
    name: str
    building: str
    capacity: int
    room_type: ClassroomType
    has_projector: bool
    has_ac: bool
    is_active: bool

    model_config = {"from_attributes": True}
