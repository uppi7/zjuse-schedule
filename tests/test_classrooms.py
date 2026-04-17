"""
tests/test_classrooms.py
教室接口测试（对应 Issue #16）。
"""

import pytest
from httpx import AsyncClient


async def test_create_classroom(client: AsyncClient):
    resp = await client.post("/api/v1/classrooms", json={
        "code": "A101",
        "name": "A座101",
        "building": "A座",
        "capacity": 120,
        "room_type": "LECTURE",
    })
    assert resp.status_code == 201
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["code"] == "A101"


async def test_create_classroom_duplicate_code(client: AsyncClient):
    payload = {"code": "B202", "name": "B202", "building": "B座", "capacity": 80, "room_type": "LECTURE"}
    await client.post("/api/v1/classrooms", json=payload)
    resp = await client.post("/api/v1/classrooms", json=payload)
    assert resp.status_code == 409


async def test_list_classrooms(client: AsyncClient):
    resp = await client.get("/api/v1/classrooms")
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_create_classroom_forbidden_for_student(student_client: AsyncClient):
    resp = await student_client.post("/api/v1/classrooms", json={
        "code": "C303",
        "name": "C303",
        "building": "C座",
        "capacity": 60,
        "room_type": "LECTURE",
    })
    assert resp.status_code == 403
