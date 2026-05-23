"""
tests/integration/test_schedule_flow.py
排课主流程集成测试：建教室 → 触发排课 → 轮询进度 → 校验落库。

Owner: tester
覆盖目标：跨服务（FastAPI + MySQL + Redis + Celery worker）的完整链路。
"""

import asyncio
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_health_endpoint_reachable(integration_client: AsyncClient):
    """示范用例：栈起来后 /health 应当返回 200。"""
    resp = await integration_client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


async def test_trigger_auto_schedule_returns_task_id(integration_client: AsyncClient):
    semester = f"it-{uuid.uuid4().hex[:8]}"

    resp = await integration_client.post(
        "/api/v1/schedule/auto-schedule",
        json={"semester": semester},
    )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["code"] == 0
    task_id = body["data"]["task_id"]
    assert task_id

    status_resp = await integration_client.get(
        f"/api/v1/schedule/schedule-status/{task_id}"
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["task_id"] == task_id


async def test_schedule_task_eventually_succeeds(integration_client: AsyncClient):
    semester = f"it-{uuid.uuid4().hex[:8]}"
    await _create_schedulable_classroom(integration_client)

    trigger = await integration_client.post(
        "/api/v1/schedule/auto-schedule",
        json={"semester": semester},
    )
    assert trigger.status_code == 202, trigger.text
    task_id = trigger.json()["data"]["task_id"]

    result_summary = None
    final_status = None
    for _ in range(20):
        await asyncio.sleep(1)
        resp = await integration_client.get(
            f"/api/v1/schedule/schedule-status/{task_id}"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        if data["status"] in ("SUCCESS", "FAILED"):
            final_status = data["status"]
            result_summary = data["result_summary"]
            break

    assert final_status == "SUCCESS", result_summary
    assert result_summary["semester"] == semester
    assert result_summary["total_courses"] >= 1
    assert result_summary["scheduled"] >= 1

    entries = await integration_client.get(
        "/api/v1/schedule/entries",
        params={"semester": semester},
    )
    assert entries.status_code == 200
    body = entries.json()
    assert body["code"] == 0
    assert len(body["data"]) >= 1


@pytest.mark.skip(reason="TODO(tester): 跨服务边界用例")
async def test_classroom_persists_across_requests(integration_client: AsyncClient):
    """
    TODO(tester):
    需求：unit 层用 SQLite in-memory 测不到的真实 MySQL 持久化，需在此处验证。

    预期成果：建一个教室 → 关闭 client → 新 client 仍能查到该教室。
    """
    raise NotImplementedError


async def _create_schedulable_classroom(integration_client: AsyncClient) -> None:
    code = f"B1-{uuid.uuid4().hex[:8]}"
    resp = await integration_client.post(
        "/api/v1/classrooms",
        json={
            "code": code,
            "name": "B1 集成测试教室",
            "campus": "玉泉",
            "building": "测试楼",
            "capacity": 80,
            "room_type": "LECTURE",
            "available_time": [
                {"day": day, "slot": slot}
                for day in range(1, 6)
                for slot in range(1, 13)
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["code"] == 0
