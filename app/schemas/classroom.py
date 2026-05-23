"""
app/schemas/classroom.py
教室资源的 Pydantic DTO（Data Transfer Object）。
"""

from pydantic import BaseModel, Field

from app.models.classroom import ClassroomType


class ClassroomSlot(BaseModel):
    """教室可用时段的单点：星期 + 节次。"""
    day: int = Field(..., ge=1, le=7, description="1=周一 … 7=周日")
    slot: int = Field(..., ge=1, le=12, description="节次 1-12")


class ClassroomCreate(BaseModel):
    code: str = Field(..., max_length=32, examples=["A101"])
    name: str = Field(..., max_length=64, examples=["A座101教室"])
    campus: str = Field(..., max_length=32, examples=["西校区"])
    building: str = Field(..., max_length=64, examples=["A座"])
    capacity: int = Field(..., gt=0, examples=[120])
    room_type: ClassroomType = ClassroomType.LECTURE
    available_time: list[ClassroomSlot] = Field(default_factory=list, description="教室基础可用时段")


class ClassroomUpdate(BaseModel):
    name: str | None = None
    campus: str | None = Field(default=None, max_length=32)
    building: str | None = Field(default=None, max_length=64)
    capacity: int | None = Field(default=None, gt=0)
    room_type: ClassroomType | None = None
    available_time: list[ClassroomSlot] | None = None
    is_active: bool | None = None


class ClassroomOut(BaseModel):
    id: int
    code: str
    name: str
    campus: str
    building: str
    capacity: int
    room_type: ClassroomType
    available_time: list[ClassroomSlot]
    is_active: bool

    model_config = {"from_attributes": True}


class ClassroomImportFailure(BaseModel):
    row: int
    code: str | None = None
    error: str


class ClassroomBatchImportResult(BaseModel):
    success: int
    failed: list[ClassroomImportFailure] = Field(default_factory=list)
