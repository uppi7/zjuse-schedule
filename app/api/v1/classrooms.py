"""
app/api/v1/classrooms.py
教室资源 CRUD 接口。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.dependencies import get_current_user, require_admin
from app.core.security import CurrentUser
from app.schemas.classroom import ClassroomCreate, ClassroomUpdate, ClassroomOut
from app.schemas.response import ApiResponse, BizCode
from app.services import classroom_service

router = APIRouter(prefix="/classrooms", tags=["教室管理"])


@router.get("", response_model=ApiResponse[list[ClassroomOut]], summary="获取教室列表")
async def list_classrooms(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    items = await classroom_service.list_classrooms(db, skip=skip, limit=limit)
    return ApiResponse.ok(data=[ClassroomOut.model_validate(i) for i in items])


@router.post("", response_model=ApiResponse[ClassroomOut], status_code=201, summary="新增教室")
async def create_classroom(
    data: ClassroomCreate,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    obj = await classroom_service.create_classroom(db, data)
    return ApiResponse.ok(data=ClassroomOut.model_validate(obj), msg="Classroom created")


@router.get("/{classroom_id}", response_model=ApiResponse[ClassroomOut], summary="获取单个教室")
async def get_classroom(
    classroom_id: int,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    obj = await classroom_service.get_classroom(db, classroom_id)
    return ApiResponse.ok(data=ClassroomOut.model_validate(obj))


@router.patch("/{classroom_id}", response_model=ApiResponse[ClassroomOut], summary="更新教室信息")
async def update_classroom(
    classroom_id: int,
    data: ClassroomUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    obj = await classroom_service.update_classroom(db, classroom_id, data)
    return ApiResponse.ok(data=ClassroomOut.model_validate(obj))


@router.delete("/{classroom_id}", response_model=ApiResponse[None], summary="删除教室")
async def delete_classroom(
    classroom_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    await classroom_service.delete_classroom(db, classroom_id)
    return ApiResponse.ok(msg="Classroom deleted")
