"""
tests/integration/test_schedule_flow.py
排课主流程集成测试：建教室 → 触发排课 → 轮询进度 → 校验落库。

Owner: tester
覆盖目标：跨服务（FastAPI + MySQL + Redis + Celery worker）的完整链路。
"""

import asyncio
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_health_endpoint_reachable(integration_client: AsyncClient):
    """示范用例：栈起来后 /health 应当返回 200。"""
    resp = await integration_client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


@pytest.mark.skip(reason="TODO(tester): 实现完整链路用例")
async def test_trigger_auto_schedule_returns_task_id(integration_client: AsyncClient):
    """
    TODO(tester):
    需求：POST /api/v1/schedule/auto-schedule 应当返回 202 + task_id。

    预期成果：
      - resp.status_code == 202
      - resp.json()["data"]["task_id"] 非空
      - 用该 task_id 调 GET /schedule-status/{task_id} 能拿到状态
    """
    raise NotImplementedError


@pytest.mark.skip(reason="TODO(tester): 实现完整链路用例")
async def test_schedule_task_eventually_succeeds(integration_client: AsyncClient):
    """
    TODO(tester):
    需求：触发排课后 Celery worker 应在 ~15s 内完成，status 变为 SUCCESS。

    预期成果：
      - 轮询 schedule-status 最终 status == "SUCCESS"
      - result_summary 含 semester / total_courses / scheduled
      - schedule_entries 表里有对应 task_id 的记录
    """
    raise NotImplementedError


@pytest.mark.skip(reason="TODO(tester): 跨服务边界用例")
async def test_classroom_persists_across_requests(integration_client: AsyncClient):
    """
    TODO(tester):
    需求：unit 层用 SQLite in-memory 测不到的真实 MySQL 持久化，需在此处验证。

    预期成果：建一个教室 → 关闭 client → 新 client 仍能查到该教室。
    """
    raise NotImplementedError
