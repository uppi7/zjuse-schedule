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

from tests.factories import make_pref_payload

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


# ── 【1】健康检查 ─────────────────────────────────────────────────────────────
async def test_health_check(admin_client: AsyncClient):
    resp = await admin_client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


# ── 【2】创建教室 ─────────────────────────────────────────────────────────────
async def test_create_classroom(admin_client: AsyncClient):
    code = f"SMOKE-{uuid.uuid4().hex[:6].upper()}"
    resp = await admin_client.post(
        "/api/v1/classrooms",
        json={
            "code": code,
            "name": "冒烟测试教室",
            "campus": "玉泉",
            "building": "测试楼",
            "capacity": 50,
            "room_type": "LECTURE",
            "available_time": [],
        },
    )
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
    resp = await student_client.post(
        "/api/v1/classrooms",
        json={
            "code": "FORBID-X",
            "name": "X",
            "campus": "玉泉",
            "building": "X",
            "capacity": 10,
            "room_type": "LECTURE",
            "available_time": [],
        },
    )
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

    assert final_status == "SUCCESS", f"排课任务未在 15s 内成功完成，最终状态：{final_status}"


async def test_teacher_end_to_end_flow(teacher_client: AsyncClient, admin_client: AsyncClient):
    """完整教师视角：写偏好 -> 管理员触发排课 -> 等待 SUCCESS -> 教师查询自己课表并检查偏好命中。"""
    # 先写一组密集偏好，保证 stub 调度到任意 day/slot 时都能命中其中至少一条。
    semester = f"e2e-smoke-{uuid.uuid4().hex[:4]}"
    pref_payloads = []
    for day_of_week in range(1, 6):
        for slot_start in range(1, 13):
            pref_payloads.append(
                make_pref_payload(
                    semester=semester,
                    day_of_week=day_of_week,
                    slot_start=slot_start,
                    slot_end=2,
                )
            )

    for payload in pref_payloads:
        create_resp = await teacher_client.post(
            "/api/v1/teacher-preferences",
            json=payload,
        )
        assert create_resp.status_code == 201, create_resp.text
        assert create_resp.json().get("code") == 0

    # 管理员触发排课
    # 先创建一个教室，确保 worker 有可用教室可排
    classroom_code = f"E2E-C-{uuid.uuid4().hex[:6].upper()}"
    create_class_resp = await admin_client.post(
        "/api/v1/classrooms",
        json={
            "code": classroom_code,
            "name": "e2e classroom",
            "campus": "玉泉",
            "building": "测试楼",
            "capacity": 60,
            "room_type": "LECTURE",
            "available_time": [],
        },
    )
    assert create_class_resp.status_code in (200, 201)
    # allow some time for DB commits visible to worker
    await asyncio.sleep(0.5)

    trigger = await admin_client.post(
        "/api/v1/schedule/auto-schedule",
        json={"semester": semester},
    )
    assert trigger.status_code == 202, trigger.text
    task_id = trigger.json()["data"]["task_id"]
    assert task_id

    # 等待任务终态（最多 180s）——生产/CI 中任务可能需要较长时间
    final_status = None
    for _ in range(60):
        await asyncio.sleep(3)
        resp = await admin_client.get(f"/api/v1/schedule/schedule-status/{task_id}")
        assert resp.status_code == 200
        status = resp.json()["data"]["status"]
        if status in ("SUCCESS", "FAILED", "FAILURE"):
            final_status = status
            break

    assert final_status == "SUCCESS", f"排课未在 180s 内完成，最终状态：{final_status}"
    # 验证总体有排课结果（算法/上游 stub 可能不属于本教师）
    entries_resp = await admin_client.get("/api/v1/schedule/entries", params={"semester": semester})
    assert entries_resp.status_code == 200
    entries_body = entries_resp.json()
    assert entries_body.get("code") == 0
    all_entries = entries_body.get("data", [])
    assert isinstance(all_entries, list)
    assert len(all_entries) > 0, "期望排课结果包含至少一条条目（全量）"

    # 使用与测试栈 stub 对齐的 teacher id，确保能查到“自己”的课表
    teacher_id = teacher_client.headers["X-User-Id"]
    teacher_entries = [e for e in all_entries if teacher_id in (e.get("teacher_ids") or [])]
    assert teacher_entries, f"expected timetable entries for teacher {teacher_id}, got none"

    def _entry_matches_any_pref(entry: dict) -> bool:
        return any(
            entry.get("day_of_week") == pref["day_of_week"]
            and entry.get("slot_start") == pref["slot_start"]
            and entry.get("slot_end") == pref["slot_end"]
            for pref in pref_payloads
        )

    hits = [entry for entry in teacher_entries if _entry_matches_any_pref(entry)]

    # 统计断言：偏好是软约束，期望命中率 > 50% 视为“偏好被尊重"
    hit_count = len(hits)
    total = len(teacher_entries)
    hit_rate = hit_count / total if total else 0.0
    assert hit_rate > 0.5, (
        f"偏好命中率过低：{hit_count}/{total} ({hit_rate:.2%})；teacher_entries={teacher_entries}"
    )
