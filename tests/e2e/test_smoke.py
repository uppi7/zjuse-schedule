"""
tests/e2e/test_smoke.py

覆盖目标：从健康检查到异步排课的完整核心路径，每次合并到主干前手动跑一遍
执行：make test-smoke

  【1】健康检查              → test_health_check
  【2】创建教室              → test_create_classroom
  【3】查询教室列表          → test_list_classrooms
  【4】权限拦截              → test_student_forbidden_to_create_classroom
  【5】触发排课              → test_trigger_auto_schedule
  【6】轮询进度直到完成      → test_schedule_task_completes
"""

import asyncio
import uuid
import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


# ── 【1】健康检查 ─────────────────────────────────────────────────────────────
async def test_health_check(admin_client: AsyncClient):
    resp = await admin_client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


# ── 【2】创建教室 ─────────────────────────────────────────────────────────────
async def test_create_classroom(admin_client: AsyncClient):
    code = f"SMOKE-{uuid.uuid4().hex[:6].upper()}"
    resp = await admin_client.post("/api/v1/classrooms", json={
        "code": code,
        "name": "冒烟测试教室",
        "campus": "玉泉",
        "building": "测试楼",
        "capacity": 50,
        "room_type": "LECTURE",
        "available_time": [],
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["code"] == 0


# ── 【3】查询教室列表 ─────────────────────────────────────────────────────────
async def test_list_classrooms(admin_client: AsyncClient):
    resp = await admin_client.get("/api/v1/classrooms")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)


# ── 【4】权限拦截 ─────────────────────────────────────────────────────────────
async def test_student_forbidden_to_create_classroom(student_client: AsyncClient):
    resp = await student_client.post("/api/v1/classrooms", json={
        "code": "FORBID-X",
        "name": "X",
        "campus": "玉泉",
        "building": "X",
        "capacity": 10,
        "room_type": "LECTURE",
        "available_time": [],
    })
    assert resp.status_code == 200
    assert resp.json()["code"] == 2012


# ── 【5+6】触发排课并轮询进度（合并为一个测试，保留 shell 中的顺序依赖语义） ──
async def test_schedule_task_completes(admin_client: AsyncClient):
    # 【5】触发
    semester = f"smoke-{uuid.uuid4().hex[:4]}"
    trigger = await admin_client.post(
        "/api/v1/schedule/auto-schedule",
        json={"semester": semester},
    )
    assert trigger.status_code == 202, trigger.text
    task_id = trigger.json()["data"]["task_id"]
    assert task_id

    # 【6】轮询：最多等待 15s，每 3s 查一次
    final_status = None
    for _ in range(5):
        await asyncio.sleep(3)
        resp = await admin_client.get(f"/api/v1/schedule/schedule-status/{task_id}")
        assert resp.status_code == 200
        status = resp.json()["data"]["status"]
        if status in ("SUCCESS", "FAILED", "FAILURE"):
            final_status = status
            break

    assert final_status == "SUCCESS", (
        f"排课任务未在 15s 内成功完成，最终状态：{final_status}"
    )
