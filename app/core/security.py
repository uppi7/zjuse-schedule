"""
app/core/security.py
解析网关透传的 HTTP Header，提取当前用户身份。
本系统不负责颁发或验证 JWT，仅消费网关已完成认证后写入 Header 的字段。
"""

from fastapi import Request, HTTPException, status
from dataclasses import dataclass
from app.core.config import settings


@dataclass
class CurrentUser:
    user_id: str
    role: str

    def is_admin(self) -> bool:
        return self.role == settings.ROLE_ADMIN

    def is_teacher(self) -> bool:
        return self.role == settings.ROLE_TEACHER

    def is_student(self) -> bool:
        return self.role == settings.ROLE_STUDENT


def parse_user_from_headers(request: Request) -> CurrentUser:
    """
    从网关透传的 Request Headers 中解析用户信息。

    TODO: [外部规范协商] 与第一组(基础信息组)及网关负责人确认：
      - 透传用户 ID 的 Header 字段名（当前假设：X-User-Id）
      - 透传用户角色的 Header 字段名（当前假设：X-User-Role）
      - 角色枚举值的具体字符串（当前假设：ADMIN / TEACHER / STUDENT）
    """
    user_id = request.headers.get(settings.AUTH_HEADER_USER_ID)
    role = request.headers.get(settings.AUTH_HEADER_USER_ROLE)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing required header: {settings.AUTH_HEADER_USER_ID}",
        )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing required header: {settings.AUTH_HEADER_USER_ROLE}",
        )

    return CurrentUser(user_id=user_id, role=role)
