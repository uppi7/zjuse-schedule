"""
app/services/classroom_service.py
教室资源 CRUD 业务逻辑。
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.classroom import Classroom
from app.schemas.classroom import ClassroomCreate, ClassroomUpdate
from app.schemas.response import BizCode


async def create_classroom(db: AsyncSession, data: ClassroomCreate) -> Classroom:
    existing = await db.scalar(select(Classroom).where(Classroom.code == data.code))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Classroom code '{data.code}' already exists",
        )
    obj = Classroom(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_classroom(db: AsyncSession, classroom_id: int) -> Classroom:
    obj = await db.get(Classroom, classroom_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": BizCode.CLASSROOM_NOT_FOUND, "msg": f"Classroom {classroom_id} not found"},
        )
    return obj


async def list_classrooms(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Classroom]:
    result = await db.execute(select(Classroom).offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_classroom(db: AsyncSession, classroom_id: int, data: ClassroomUpdate) -> Classroom:
    obj = await get_classroom(db, classroom_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_classroom(db: AsyncSession, classroom_id: int) -> None:
    obj = await get_classroom(db, classroom_id)
    await db.delete(obj)
    await db.commit()
