"""
app/core/external_clients.py
跨微服务 HTTP 调用封装，基于 httpx.AsyncClient。
所有对外部子系统的调用都集中在此文件，便于统一管理超时、Mock、契约调整。

鉴权约定：
   子系统间默认互信；
   调用上游时透传当前用户身份：
     X-User-Id   : 调用者 user_id（在排课任务里 = 触发排课的管理员 id）
     X-User-Role : 调用者角色（ADMIN / TEACHER / STUDENT）
"""

from typing import Any
import httpx
from app.core.config import settings


def _trust_headers(user_id: str, role: str) -> dict[str, str]:
    """构造对上游服务的互信 Header（透传调用者身份）。"""
    return {
        settings.AUTH_HEADER_USER_ID: user_id,
        settings.AUTH_HEADER_USER_ROLE: role,
    }


class InfoServiceClient:
    """
    封装对第一子系统（基础信息管理组）的 HTTP 调用。

      GET /api/v1/courses?semester={semester}    scope: course:read
      GET /api/v1/courses/{course_id}            scope: course:read     （排课暂未使用）

    响应包络（约定）：
      {"code": 0, "msg": "success", "data": [...] | {...}}

    课程列表每条记录字段（**算法必需，第一组返回这些字段**）：
      course_id     : str    课程唯一标识
      name          : str    课程名称
      teacher_id    : str    主讲教师 ID（合上课暂按单教师处理）
      semester      : str    学期标识，如 "2024-2025-1"
      weekly_hours  : int    每周课时数
      student_count : int    选课人数
      needs_lab     : bool   是否需要实验室
    """

    def __init__(self, user_id: str, role: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.INFO_SERVICE_BASE_URL,
            headers=_trust_headers(user_id, role),
            timeout=10.0,
        )

    @staticmethod
    def _unwrap(body: Any) -> Any:
        """解开 {code,msg,data} 包络；兼容直接返回 list/dict 的情况。"""
        return body["data"] if isinstance(body, dict) and "data" in body else body

    async def get_all_courses(self, semester: str) -> list[dict[str, Any]]:
        """
        拉取指定学期的全部课程基本信息。
        返回元素结构见类 docstring。
        """
        resp = await self._client.get(
            settings.INFO_SERVICE_COURSES_PATH, params={"semester": semester}
        )
        resp.raise_for_status()
        return self._unwrap(resp.json())

    async def aclose(self) -> None:
        await self._client.aclose()
