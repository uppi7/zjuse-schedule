"""
app/core/external_clients.py
跨微服务 HTTP 调用封装，基于 httpx.AsyncClient。
所有对外部子系统的调用都集中在此文件，便于统一管理超时、重试和 Mock。
"""

from typing import Any
import httpx
from app.core.config import settings


# ── HTTP 客户端工厂 ────────────────────────────────────────────────────────

def _make_client(base_url: str, timeout: float = 10.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, timeout=timeout)


# ── 基础信息组客户端（第一子系统） ────────────────────────────────────────

class InfoServiceClient:
    """
    封装对第一子系统（基础信息管理组）的 HTTP 调用。

    TODO: [外部规范协商] 与第一组(基础信息组)确认以下所有信息：
      1. 内网服务名称与端口（当前配置：INFO_SERVICE_BASE_URL=http://info-service:8000）
      2. 教师列表 API 路径（当前假设：GET /api/v1/teachers）
      3. 课程列表 API 路径（当前假设：GET /api/v1/courses）
      4. 教室列表 API 路径（当前假设：GET /api/v1/classrooms）
      5. 以上接口返回的 JSON 结构（字段名、嵌套层级、分页方式）
    """

    def __init__(self) -> None:
        self._client = _make_client(settings.INFO_SERVICE_BASE_URL)

    async def get_all_teachers(self) -> list[dict[str, Any]]:
        """
        拉取全量教师列表。

        TODO: [外部规范协商] 确认返回结构，示例假设：
          [{"teacher_id": "T001", "name": "张三", "available_slots": [...]}]
        """
        resp = await self._client.get(settings.INFO_SERVICE_TEACHERS_PATH)
        resp.raise_for_status()
        # TODO: 根据实际返回结构调整解包方式，例如 resp.json()["data"]
        return resp.json()

    async def get_all_courses(self) -> list[dict[str, Any]]:
        """
        拉取全量课程列表。

        TODO: [外部规范协商] 确认返回结构，示例假设：
          [{"course_id": "C001", "name": "高等数学", "credit": 3,
            "weekly_hours": 4, "teacher_id": "T001", "student_count": 60}]
        """
        resp = await self._client.get(settings.INFO_SERVICE_COURSES_PATH)
        resp.raise_for_status()
        return resp.json()

    async def get_all_classrooms(self) -> list[dict[str, Any]]:
        """
        拉取全量教室列表（也可从本地 DB 读取，两者均保留）。

        TODO: [外部规范协商] 确认是否需要从第一组拉取教室，
              或由排课组自行维护教室数据（当前方案：本组维护，但保留此接口备用）。
        """
        resp = await self._client.get(settings.INFO_SERVICE_CLASSROOMS_PATH)
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._client.aclose()


# ── 单例（在 lifespan 中初始化与销毁） ───────────────────────────────────

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
