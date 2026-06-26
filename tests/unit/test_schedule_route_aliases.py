"""
tests/unit/test_schedule_route_aliases.py
Schedule-prefix aliases for classroom and teacher preference routes.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.main import app

pytestmark = pytest.mark.unit


def _code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _teacher_client_for(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-User-Id": "alias-teacher-001", "X-User-Role": "TEACHER"},
    )


async def test_schedule_classrooms_alias_reuses_crud_behavior(client: AsyncClient):
    code = _code("ALIASROOM")
    create_resp = await client.post(
        "/api/v1/schedule/classrooms",
        json={
            "code": code,
            "name": "别名路由教室",
            "campus": "玉泉",
            "building": "教三",
            "capacity": 80,
            "room_type": "LECTURE",
            "available_time": [{"day": 1, "slot": 1}],
        },
    )

    assert create_resp.status_code == 201
    assert create_resp.json()["code"] == 0
    classroom_id = create_resp.json()["data"]["id"]

    list_resp = await client.get("/api/v1/schedule/classrooms")
    assert list_resp.status_code == 200
    assert any(item["code"] == code for item in list_resp.json()["data"])

    patch_resp = await client.patch(
        f"/api/v1/schedule/classrooms/{classroom_id}",
        json={"is_active": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["is_active"] is False


async def test_schedule_teacher_preferences_alias_reuses_current_user_behavior(
    db_session: AsyncSession,
):
    async with await _teacher_client_for(db_session) as teacher_client:
        payload = {
            "semester": f"alias-{uuid.uuid4().hex[:8]}",
            "course_id": "ALIAS-COURSE",
            "day_of_week": 2,
            "slot_start": 3,
            "slot_end": 4,
            "week_start": 1,
            "week_end": 16,
            "week_parity": "ALL",
            "is_negative": False,
        }
        create_resp = await teacher_client.post(
            "/api/v1/schedule/teacher-preferences",
            json=payload,
        )

        assert create_resp.status_code == 201
        assert create_resp.json()["code"] == 0
        assert create_resp.json()["data"]["teacher_id"] == "alias-teacher-001"

        list_resp = await teacher_client.get(
            "/api/v1/schedule/teacher-preferences",
            params={"semester": payload["semester"]},
        )
        assert list_resp.status_code == 200
        assert [item["course_id"] for item in list_resp.json()["data"]] == ["ALIAS-COURSE"]

    app.dependency_overrides.clear()
