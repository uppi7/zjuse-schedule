"""
app/api/v1/teacher_preferences.py
教师排课偏好 CRUD 接口。

身份语义：教师自助提交。teacher_id 从 X-User-Id 自动绑定（require_teacher_or_admin），
请求体里不出现 teacher_id 字段。Admin 角色亦可通过此接口提交，但写入的 teacher_id
即为 admin 自己的 user_id（admin 代提交不在本期范围）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.dependencies import require_teacher_or_admin
from app.core.security import CurrentUser
from app.schemas.response import ApiResponse
from app.schemas.teacher_preference import (
    TeacherPreferenceCreate, TeacherPreferenceUpdate, TeacherPreferenceOut,
)
from app.services import teacher_preference_service

router = APIRouter(prefix="/teacher-preferences", tags=["教师偏好"])


@router.post(
    "",
    response_model=ApiResponse[TeacherPreferenceOut],
    status_code=201,
    summary="新增教师偏好",
)
async def create_preference(
    data: TeacherPreferenceCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_teacher_or_admin),
):
    obj = await teacher_preference_service.create_preference(db, user.user_id, data)
    return ApiResponse.ok(data=TeacherPreferenceOut.model_validate(obj), msg="Preference created")


@router.get(
    "",
    response_model=ApiResponse[list[TeacherPreferenceOut]],
    summary="列出当前用户的偏好",
)
async def list_preferences(
    semester: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_teacher_or_admin),
):
    items = await teacher_preference_service.list_preferences(
        db, user.user_id, semester=semester, skip=skip, limit=limit,
    )
    return ApiResponse.ok(data=[TeacherPreferenceOut.model_validate(i) for i in items])


@router.get(
    "/{pref_id}",
    response_model=ApiResponse[TeacherPreferenceOut],
    summary="获取单条偏好",
)
async def get_preference(
    pref_id: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_teacher_or_admin),
):
    obj = await teacher_preference_service.get_preference(db, pref_id, user.user_id)
    return ApiResponse.ok(data=TeacherPreferenceOut.model_validate(obj))


@router.patch(
    "/{pref_id}",
    response_model=ApiResponse[TeacherPreferenceOut],
    summary="更新偏好（PATCH，半字段）",
)
async def update_preference(
    pref_id: int,
    data: TeacherPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_teacher_or_admin),
):
    obj = await teacher_preference_service.update_preference(db, pref_id, user.user_id, data)
    return ApiResponse.ok(data=TeacherPreferenceOut.model_validate(obj))


@router.delete(
    "/{pref_id}",
    response_model=ApiResponse[None],
    summary="删除偏好",
)
async def delete_preference(
    pref_id: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_teacher_or_admin),
):
    await teacher_preference_service.delete_preference(db, pref_id, user.user_id)
    return ApiResponse.ok(msg="Preference deleted")
