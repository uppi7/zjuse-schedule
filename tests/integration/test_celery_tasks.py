"""
tests/integration/test_celery_tasks.py
Celery 任务集成测试：通过真实 worker 验证任务派发/重试/状态汇报。

Owner: tester
覆盖目标：scheduler.run_auto_schedule 任务的全生命周期。
"""

import asyncio
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.algorithm.engine import ClassroomInput, CourseInput, RoomRequirement, RoomType
from app.tasks import scheduler_tasks

pytestmark = pytest.mark.integration

_TERMINAL_SCHEDULE_STATES = {"SUCCESS", "FAILED", "PARTIAL"}
_REDIS_META_STATES = {"PROGRESS", "SUCCESS", "FAILURE"}


async def test_run_auto_schedule_dispatched_to_worker(
    integration_client: AsyncClient,
    integration_mysql_engine: AsyncEngine,
    integration_redis_client,
):
    semester = f"it-{uuid.uuid4().hex[:8]}"
    task_id = None

    try:
        resp = await integration_client.post(
            "/api/v1/schedule/auto-schedule",
            json={"semester": semester},
        )

        assert resp.status_code == 202, resp.text
        task_id = resp.json()["data"]["task_id"]
        assert task_id

        meta = await _wait_for_redis_meta_state(
            integration_redis_client,
            task_id,
        )
        assert meta["status"] in _REDIS_META_STATES
        assert meta["status"] in {"PROGRESS", "SUCCESS", "FAILURE"}
    finally:
        if task_id:
            await _wait_for_task_terminal_state(integration_client, task_id)
            await _cleanup_schedule_artifacts(integration_mysql_engine, task_id, semester)


async def test_progress_updates_visible_during_execution(
    integration_client: AsyncClient,
    integration_mysql_engine: AsyncEngine,
):
    semester = f"it-{uuid.uuid4().hex[:8]}"
    task_id = None
    classroom_codes: list[str] = []

    for _ in range(5):
        classroom_code = f"PGR-{uuid.uuid4().hex[:8]}"
        classroom_codes.append(classroom_code)
        create = await integration_client.post(
            "/api/v1/classrooms",
            json={
                "code": classroom_code,
                "name": "进度测试教室",
                "campus": "玉泉",
                "building": "测试楼",
                "capacity": 10,
                "room_type": "LECTURE",
                "available_time": [
                    {"day": day, "slot": slot} for day in range(1, 6) for slot in range(1, 13)
                ],
            },
        )
        assert create.status_code == 201, create.text

    try:
        resp = await integration_client.post(
            "/api/v1/schedule/auto-schedule",
            json={"semester": semester},
        )
        assert resp.status_code == 202, resp.text
        task_id = resp.json()["data"]["task_id"]

        seen_progress = False
        final_status = None
        for _ in range(600):
            poll = await integration_client.get(f"/api/v1/schedule/schedule-status/{task_id}")
            assert poll.status_code == 200, poll.text
            data = poll.json()["data"]
            if data["status"] == "RUNNING" and 0 < data["progress"] < 100:
                seen_progress = True
                break
            if data["status"] in _TERMINAL_SCHEDULE_STATES:
                final_status = data["status"]
                break
            await asyncio.sleep(0.02)

        assert seen_progress, final_status
    finally:
        if task_id:
            await _wait_for_task_terminal_state(integration_client, task_id)
            await _cleanup_schedule_artifacts(integration_mysql_engine, task_id, semester)
        for classroom_code in classroom_codes:
            await _delete_classroom_by_code(integration_mysql_engine, classroom_code)


async def test_task_failure_triggers_retry(monkeypatch):
    semester = f"it-{uuid.uuid4().hex[:8]}"
    task_id = f"celery-{uuid.uuid4().hex}"
    attempts = {"count": 0}
    final_failure = {"count": 0}

    async def fake_fetch_upstream_data(semester_arg: str, triggered_by: str):
        attempts["count"] += 1
        raise RuntimeError("upstream down")

    async def fake_mark_task_running(task_id_arg: str) -> None:
        return None

    async def fake_mark_task_failed_and_dispose(task_id_arg: str, exc: Exception) -> None:
        final_failure["count"] += 1

    monkeypatch.setattr(
        scheduler_tasks,
        "_fetch_upstream_data",
        fake_fetch_upstream_data,
    )
    monkeypatch.setattr(scheduler_tasks, "_mark_task_running", fake_mark_task_running)
    monkeypatch.setattr(
        scheduler_tasks,
        "_mark_task_failed_and_dispose",
        fake_mark_task_failed_and_dispose,
    )
    monkeypatch.setattr(
        scheduler_tasks.run_auto_schedule,
        "update_state",
        lambda *args, **kwargs: None,
    )

    await asyncio.to_thread(
        lambda: scheduler_tasks.run_auto_schedule.apply(
            args=(semester, "integration-admin"), task_id=task_id
        )
    )

    assert attempts["count"] == 3
    assert final_failure["count"] == 1


async def test_partial_results_mark_task_partial(monkeypatch):
    semester = f"it-{uuid.uuid4().hex[:8]}"
    task_id = f"celery-{uuid.uuid4().hex}"
    captured: dict[str, object] = {}

    async def fake_fetch_upstream_data(semester_arg: str, triggered_by: str):
        return (
            [
                CourseInput(
                    course_id="O001",
                    teacher_ids=["T001"],
                    student_count=10,
                    room_requirements=[RoomRequirement(RoomType.LECTURE, 2)],
                ),
                CourseInput(
                    course_id="O002",
                    teacher_ids=["T002"],
                    student_count=200,
                    room_requirements=[RoomRequirement(RoomType.LECTURE, 2)],
                ),
            ],
            [
                ClassroomInput(
                    classroom_id=1,
                    campus="玉泉",
                    capacity=30,
                    room_type=RoomType.LECTURE,
                    available_slots={(day, slot) for day in range(1, 6) for slot in range(1, 13)},
                )
            ],
            [],
            {
                "O001": {
                    "course_id": "C001",
                    "course_code": "CS001",
                    "course_name": "Algorithms",
                },
                "O002": {
                    "course_id": "C002",
                    "course_code": "CS002",
                    "course_name": "Data Structures",
                },
            },
        )

    async def fake_mark_task_running(task_id_arg: str) -> None:
        captured["task_id"] = task_id_arg

    async def fake_save_results(task_id_arg: str, semester_arg: str, results, unscheduled):
        captured["task_status"] = "PARTIAL" if unscheduled else "SUCCESS"
        captured["semester"] = semester_arg
        captured["scheduled_count"] = len(results)
        captured["unscheduled"] = list(unscheduled)

    async def fake_notify_downstream(semester_arg: str) -> None:
        return None

    monkeypatch.setattr(scheduler_tasks, "_fetch_upstream_data", fake_fetch_upstream_data)
    monkeypatch.setattr(scheduler_tasks, "_mark_task_running", fake_mark_task_running)
    monkeypatch.setattr(scheduler_tasks, "_save_results", fake_save_results)
    monkeypatch.setattr(scheduler_tasks, "_notify_downstream", fake_notify_downstream)
    monkeypatch.setattr(
        scheduler_tasks.run_auto_schedule,
        "update_state",
        lambda *args, **kwargs: None,
    )

    await asyncio.to_thread(
        lambda: scheduler_tasks.run_auto_schedule.apply(
            args=(semester, "integration-admin"), task_id=task_id
        )
    )

    assert captured["task_id"] == task_id
    assert captured["semester"] == semester
    assert captured["task_status"] == "PARTIAL"
    assert captured["scheduled_count"] >= 1
    assert captured["unscheduled"] == ["O002"]


async def _wait_for_redis_meta_state(
    redis_client,
    task_id: str,
    timeout_seconds: int = 60,
):
    key = f"celery-task-meta-{task_id}"
    for _ in range(timeout_seconds * 10):
        raw = await redis_client.get(key)
        if raw:
            meta = json.loads(raw)
            if meta.get("status") in _REDIS_META_STATES:
                return meta
        await asyncio.sleep(0.1)
    raise AssertionError(f"task {task_id} did not produce a stable redis meta state")


async def _wait_for_task_terminal_state(
    integration_client: AsyncClient,
    task_id: str,
    timeout_seconds: int = 75,
) -> str:
    for _ in range(timeout_seconds):
        resp = await integration_client.get(f"/api/v1/schedule/schedule-status/{task_id}")
        assert resp.status_code == 200, resp.text
        status = resp.json()["data"]["status"]
        if status in _TERMINAL_SCHEDULE_STATES:
            return status
        await asyncio.sleep(1)
    raise AssertionError(f"task {task_id} did not reach terminal state within {timeout_seconds}s")


async def _cleanup_schedule_artifacts(
    integration_mysql_engine: AsyncEngine,
    task_id: str,
    semester: str,
) -> None:
    async with integration_mysql_engine.begin() as conn:
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


async def _delete_classroom_by_code(
    integration_mysql_engine: AsyncEngine,
    classroom_code: str,
) -> None:
    async with integration_mysql_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM classrooms WHERE code = :code"),
            {"code": classroom_code},
        )
