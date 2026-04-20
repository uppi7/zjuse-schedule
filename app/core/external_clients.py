"""
app/core/external_clients.py
跨微服务 HTTP 调用封装，基于 httpx.AsyncClient。
所有对外部子系统的调用都集中在此文件，便于统一管理超时、重试和 Mock。
"""

from typing import Any
import httpx
from app.core.config import settings


def _make_client(base_url: str, timeout: float = 10.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, timeout=timeout)


class InfoServiceClient:
    """
    封装对第一子系统（基础信息管理组）的 HTTP 调用。

    约定的响应格式（与基础信息组对齐）：
      {"code": 0, "msg": "success", "data": [...]}

    教师列表每条记录字段：
      teacher_id  : str   — 教师唯一标识
      name        : str   — 姓名

    课程列表每条记录字段：
      course_id     : str   — 课程唯一标识
      name          : str   — 课程名称
      teacher_id    : str   — 授课教师 ID
      weekly_hours  : int   — 每周课时数
      student_count : int   — 选课学生人数
      needs_lab     : bool  — 是否需要实验室（默认 false）
    """

    def __init__(self) -> None:
        self._client = _make_client(settings.INFO_SERVICE_BASE_URL)

    async def get_all_teachers(self) -> list[dict[str, Any]]:
        resp = await self._client.get(settings.INFO_SERVICE_TEACHERS_PATH)
        resp.raise_for_status()
        body = resp.json()
        return body["data"] if isinstance(body, dict) else body

    async def get_all_courses(self) -> list[dict[str, Any]]:
        resp = await self._client.get(settings.INFO_SERVICE_COURSES_PATH)
        resp.raise_for_status()
        body = resp.json()
        return body["data"] if isinstance(body, dict) else body

    async def aclose(self) -> None:
        await self._client.aclose()


# ── 单例（在 lifespan 中初始化与销毁）────────────────────────────────────

_info_client: InfoServiceClient | None = None


def get_info_client() -> InfoServiceClient:
    global _info_client
    if _info_client is None:
        _info_client = InfoServiceClient()
    return _info_client


async def close_info_client() -> None:
    global _info_client
    if _info_client is not None:
        await _info_client.aclose()
        _info_client = None
