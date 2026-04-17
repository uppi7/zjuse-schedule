"""
app/api/dependencies.py
FastAPI 通用依赖注入：当前用户、数据库 Session、权限校验。
"""

from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, parse_user_from_headers
from app.core.config import settings


def get_current_user(request: Request) -> CurrentUser:
    """
    从网关透传的 Headers 中解析当前登录用户。
    如果 Header 缺失，抛出 401。

    TODO: [外部规范协商] 与第一组及网关负责人确认 Header 字段名和 Role Code 后
    在 app/core/config.py 中更新 AUTH_HEADER_USER_ID / AUTH_HEADER_USER_ROLE。
    """
    return parse_user_from_headers(request)


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """权限拦截：仅允许教务管理员操作。"""
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required role: {settings.ROLE_ADMIN}, current role: {current_user.role}",
        )
    return current_user


def require_teacher_or_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """权限拦截：教师或管理员均可操作。"""
    if not (current_user.is_admin() or current_user.is_teacher()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher or Admin role required",
        )
    return current_user
