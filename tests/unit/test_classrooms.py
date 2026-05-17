"""
tests/unit/test_classrooms.py
教室接口单元测试（ASGITransport + SQLite in-memory，无外部依赖）
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.unit

async def test_create_classroom(client: AsyncClient):
    resp = await client.post("/api/v1/classrooms", json={
        "code": "101",
        "name": "琴房一",
        "campus": "紫金港",
        "building": "西教",
        "capacity": 120,
        "room_type": "LECTURE",
        "available_time": [{"day": 1, "slot": 1}, {"day": 1, "slot": 2}],
    })
    assert resp.status_code == 201
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["code"] == "A101"


async def test_create_classroom_duplicate_code(client: AsyncClient):
    payload = {
        "code": "202",
        "name": "202",
        "campus": "玉泉",
        "building": "教四",
        "capacity": 80,
        "room_type": "LECTURE",
        "available_time": [],
    }
    await client.post("/api/v1/classrooms", json=payload)
    resp = await client.post("/api/v1/classrooms", json=payload)
    assert resp.status_code == 409


async def test_list_classrooms(client: AsyncClient):
    resp = await client.get("/api/v1/classrooms")
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_create_classroom_forbidden_for_student(student_client: AsyncClient):
    resp = await student_client.post("/api/v1/classrooms", json={
        "code": "303",
        "name": "303",
        "campus": "玉泉",
        "building": "教七",
        "capacity": 60,
        "room_type": "LECTURE",
        "available_time": [],
    })
    assert resp.status_code == 403
