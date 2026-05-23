"""
app/api/v1/classrooms.py
教室资源 CRUD 接口。
"""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import CurrentUser
from app.schemas.classroom import (
    ClassroomBatchImportResult,
    ClassroomCreate,
    ClassroomOut,
    ClassroomUpdate,
)
from app.schemas.response import ApiResponse, BizCode, BizException
from app.services import classroom_service

router = APIRouter(prefix="/classrooms", tags=["教室管理"])

CLASSROOM_BATCH_IMPORT_DESCRIPTION = """
上传 `.csv` 或 `.xlsx` 文件批量导入教室，文件大小不超过 5 MB。

文件首行为表头。必填列：`code`, `name`, `campus`, `building`, `capacity`。
可选列：`room_type`, `available_time`, `is_active`。

`available_time` 使用逗号分隔的 `星期-节次` 字符串，例如 `1-1,1-2,2-3`；
空值表示教室基础可用时段为空数组。已存在 `code` 默认跳过，
传 `overwrite=true` 时覆盖更新。
"""


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


@router.post(
    "/batch-import",
    response_model=ApiResponse[ClassroomBatchImportResult],
    summary="批量导入教室",
    description=CLASSROOM_BATCH_IMPORT_DESCRIPTION,
)
async def batch_import_classrooms(
    overwrite: bool = False,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    content = await file.read(classroom_service.MAX_IMPORT_FILE_SIZE + 1)
    if len(content) > classroom_service.MAX_IMPORT_FILE_SIZE:
        raise BizException(BizCode.VALIDATION_ERROR, "上传文件不能超过 5 MB")

    result = await classroom_service.batch_import_classrooms(
        db,
        filename=file.filename or "",
        content=content,
        overwrite=overwrite,
    )
    return ApiResponse.ok(data=result)


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
