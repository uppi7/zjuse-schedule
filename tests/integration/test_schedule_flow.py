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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

_TERMINAL_SCHEDULE_STATES = {"SUCCESS", "FAILED", "PARTIAL"}


async def test_health_endpoint_reachable(integration_client: AsyncClient):
    """示范用例：栈起来后 /health 应当返回 200。"""
    resp = await integration_client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


async def test_trigger_auto_schedule_returns_task_id(
    integration_client: AsyncClient,
    integration_mysql_engine: AsyncEngine,
):
    semester = f"it-{uuid.uuid4().hex[:8]}"
    classroom_code = f"B1-{uuid.uuid4().hex[:8]}"
    task_id = None

    await _create_schedulable_classroom(integration_client, classroom_code)

    try:
        resp = await integration_client.post(
            "/api/v1/schedule/auto-schedule",
            json={"semester": semester},
        )

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["code"] == 0
        task_id = body["data"]["task_id"]
        assert task_id

        status_resp = await integration_client.get(f"/api/v1/schedule/schedule-status/{task_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["data"]["task_id"] == task_id

        await _wait_for_schedule_terminal_state(integration_client, task_id)
    finally:
        if task_id:
            await _cleanup_schedule_artifacts(
                integration_mysql_engine,
                task_id,
                semester,
            )
        await _delete_classroom_by_code(integration_mysql_engine, classroom_code)


async def test_schedule_task_eventually_succeeds(
    integration_client: AsyncClient,
    integration_mysql_engine: AsyncEngine,
):
    semester = f"it-{uuid.uuid4().hex[:8]}"
    classroom_code = f"B1-{uuid.uuid4().hex[:8]}"
    task_id = None

    await _create_schedulable_classroom(integration_client, classroom_code)

    try:
        trigger = await integration_client.post(
            "/api/v1/schedule/auto-schedule",
            json={"semester": semester},
        )
        assert trigger.status_code == 202, trigger.text
        task_id = trigger.json()["data"]["task_id"]

        result_summary = None
        final_status = None
        for _ in range(60):
            await asyncio.sleep(1)
            resp = await integration_client.get(f"/api/v1/schedule/schedule-status/{task_id}")
            assert resp.status_code == 200
            data = resp.json()["data"]
            if data["status"] in _TERMINAL_SCHEDULE_STATES:
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

        assert (
            await _count_schedule_entries_for_task(
                integration_mysql_engine,
                task_id,
                semester,
            )
            >= 1
        )
    finally:
        if task_id:
            await _cleanup_schedule_artifacts(
                integration_mysql_engine,
                task_id,
                semester,
            )
        await _delete_classroom_by_code(integration_mysql_engine, classroom_code)


async def test_classroom_persists_across_requests(
    integration_client: AsyncClient,
    integration_mysql_engine: AsyncEngine,
):
    code = f"B1-{uuid.uuid4().hex[:8]}"
    classroom_id = None

    try:
        create_resp = await integration_client.post(
            "/api/v1/classrooms",
            json={
                "code": code,
                "name": "B1 持久化教室",
                "campus": "玉泉",
                "building": "测试楼",
                "capacity": 66,
                "room_type": "LECTURE",
                "available_time": [{"day": 1, "slot": 1}],
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        classroom_id = create_resp.json()["data"]["id"]

        async with AsyncClient(
            base_url=str(integration_client.base_url),
            headers={
                "X-User-Id": "integration-admin-2",
                "X-User-Role": "SYS_ADMIN",
            },
            timeout=60.0,
        ) as new_client:
            get_resp = await new_client.get(f"/api/v1/classrooms/{classroom_id}")
            assert get_resp.status_code == 200, get_resp.text
            assert get_resp.json()["data"]["code"] == code

        row = await _fetch_classroom_by_code(integration_mysql_engine, code)
        assert row is not None
        assert row[0] == classroom_id
    finally:
        await _delete_classroom_by_code(integration_mysql_engine, code)


async def test_duplicate_trigger_is_rejected_when_same_semester_running(
    integration_client: AsyncClient,
    integration_mysql_engine: AsyncEngine,
):
    semester = f"it-{uuid.uuid4().hex[:8]}"
    classroom_code = f"B1-{uuid.uuid4().hex[:8]}"
    task_id = None

    await _create_schedulable_classroom(integration_client, classroom_code)

    try:
        first = await integration_client.post(
            "/api/v1/schedule/auto-schedule",
            json={"semester": semester},
        )
        assert first.status_code == 202, first.text
        task_id = first.json()["data"]["task_id"]

        second = await integration_client.post(
            "/api/v1/schedule/auto-schedule",
            json={"semester": semester},
        )
        assert second.status_code == 200
        assert second.json()["code"] == 2004
    finally:
        if task_id:
            await _wait_for_schedule_terminal_state(integration_client, task_id)
            await _cleanup_schedule_artifacts(
                integration_mysql_engine,
                task_id,
                semester,
            )
        await _delete_classroom_by_code(integration_mysql_engine, classroom_code)


async def _create_schedulable_classroom(
    integration_client: AsyncClient,
    code: str,
) -> None:
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
                {"day": day, "slot": slot} for day in range(1, 6) for slot in range(1, 13)
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["code"] == 0


async def _wait_for_schedule_terminal_state(
    integration_client: AsyncClient,
    task_id: str,
    timeout_seconds: int = 60,
) -> str:
    for _ in range(timeout_seconds):
        resp = await integration_client.get(f"/api/v1/schedule/schedule-status/{task_id}")
        assert resp.status_code == 200, resp.text
        status = resp.json()["data"]["status"]
        if status in _TERMINAL_SCHEDULE_STATES:
            return status
        await asyncio.sleep(1)
    raise AssertionError(f"task {task_id} did not reach terminal state within {timeout_seconds}s")


async def _count_schedule_entries_for_task(
    engine: AsyncEngine,
    task_id: str,
    semester: str,
) -> int:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM schedule_entries e
                JOIN schedule_tasks t ON e.task_id = t.id
                WHERE t.celery_task_id = :task_id AND e.semester = :semester
                """
            ),
            {"task_id": task_id, "semester": semester},
        )
        return int(result.scalar_one())


async def _fetch_classroom_by_code(
    engine: AsyncEngine,
    code: str,
):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT id, code
                FROM classrooms
                WHERE code = :code
                LIMIT 1
                """
            ),
            {"code": code},
        )
        return result.first()


async def _delete_classroom_by_code(
    engine: AsyncEngine,
    code: str,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM classrooms WHERE code = :code"),
            {"code": code},
        )


async def _cleanup_schedule_artifacts(
    engine: AsyncEngine,
    task_id: str,
    semester: str,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                DELETE e
                FROM schedule_entries e
                JOIN schedule_tasks t ON e.task_id = t.id
                WHERE t.celery_task_id = :task_id AND e.semester = :semester
                """
            ),
            {"task_id": task_id, "semester": semester},
        )
        await conn.execute(
            text("DELETE FROM schedule_tasks WHERE celery_task_id = :task_id"),
            {"task_id": task_id},
        )
