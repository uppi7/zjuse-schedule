"""
tests/unit/test_teacher_timetable.py
教师课表查询接口单元测试。
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.main import app
from app.models.schedule import (
    DayOfWeek,
    ScheduleEntry,
    ScheduleStatus,
    ScheduleTask,
    WeekParity,
)

pytestmark = pytest.mark.unit


def _semester() -> str:
    return f"b3-{uuid.uuid4().hex[:8]}"


async def _client_for(db_session: AsyncSession, user_id: str, role: str) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-User-Id": user_id, "X-User-Role": role},
    )


@pytest.fixture
async def admin_client(db_session: AsyncSession):
    async with await _client_for(db_session, "admin-b3-001", "ADMIN") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def teacher_client(db_session: AsyncSession):
    async with await _client_for(db_session, "teacher-b3-001", "TEACHER") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def other_teacher_client(db_session: AsyncSession):
    async with await _client_for(db_session, "teacher-b3-002", "TEACHER") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_task(db_session: AsyncSession, semester: str) -> ScheduleTask:
    task = ScheduleTask(
        celery_task_id=f"b3-{uuid.uuid4().hex}",
        semester=semester,
        status=ScheduleStatus.SUCCESS,
        triggered_by="admin-b3-001",
    )
    db_session.add(task)
    await db_session.flush()
    return task


async def _add_entry(
    db_session: AsyncSession,
    task: ScheduleTask,
    *,
    semester: str,
    course_id: str,
    teacher_ids: list[str],
    week_start: int = 1,
    week_end: int = 16,
    week_parity: WeekParity = WeekParity.ALL,
) -> ScheduleEntry:
    entry = ScheduleEntry(
        task_id=task.id,
        semester=semester,
        course_id=course_id,
        teacher_ids=teacher_ids,
        classroom_id=1,
        day_of_week=DayOfWeek.MON,
        slot_start=1,
        slot_end=2,
        week_start=week_start,
        week_end=week_end,
        week_parity=week_parity,
    )
    db_session.add(entry)
    await db_session.flush()
    return entry


async def _get_timetable(
    client: AsyncClient,
    teacher_id: str,
    *,
    semester: str,
    week: int | None = None,
):
    params: dict[str, str | int] = {"semester": semester}
    if week is not None:
        params["week"] = week
    resp = await client.get(
        f"/api/v1/schedule/teachers/{teacher_id}/timetable",
        params=params,
    )
    assert resp.status_code == 200
    return resp.json()


async def test_week_filter_includes_all_parity(
    db_session: AsyncSession,
    teacher_client: AsyncClient,
):
    semester = _semester()
    task = await _seed_task(db_session, semester)
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="B3-ALL",
        teacher_ids=["teacher-b3-001"],
        week_parity=WeekParity.ALL,
    )
    await db_session.commit()

    body = await _get_timetable(
        teacher_client,
        "teacher-b3-001",
        semester=semester,
        week=2,
    )

    assert body["code"] == 0
    assert [entry["course_id"] for entry in body["data"]["entries"]] == ["B3-ALL"]


async def test_week_filter_applies_odd_and_even_parity(
    db_session: AsyncSession,
    teacher_client: AsyncClient,
):
    semester = _semester()
    task = await _seed_task(db_session, semester)
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="B3-ODD",
        teacher_ids=["teacher-b3-001"],
        week_parity=WeekParity.ODD,
    )
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="B3-EVEN",
        teacher_ids=["teacher-b3-001"],
        week_parity=WeekParity.EVEN,
    )
    await db_session.commit()

    odd_body = await _get_timetable(
        teacher_client,
        "teacher-b3-001",
        semester=semester,
        week=3,
    )
    even_body = await _get_timetable(
        teacher_client,
        "teacher-b3-001",
        semester=semester,
        week=4,
    )

    assert [entry["course_id"] for entry in odd_body["data"]["entries"]] == ["B3-ODD"]
    assert [entry["course_id"] for entry in even_body["data"]["entries"]] == ["B3-EVEN"]


async def test_week_filter_respects_week_range(
    db_session: AsyncSession,
    teacher_client: AsyncClient,
):
    semester = _semester()
    task = await _seed_task(db_session, semester)
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="B3-FIRST-HALF",
        teacher_ids=["teacher-b3-001"],
        week_start=1,
        week_end=8,
        week_parity=WeekParity.ALL,
    )
    await db_session.commit()

    body = await _get_timetable(
        teacher_client,
        "teacher-b3-001",
        semester=semester,
        week=9,
    )

    assert body["code"] == 0
    assert body["data"]["entries"] == []


async def test_without_week_returns_whole_semester_without_parity_filter(
    db_session: AsyncSession,
    teacher_client: AsyncClient,
):
    semester = _semester()
    task = await _seed_task(db_session, semester)
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="B3-ODD-WHOLE",
        teacher_ids=["teacher-b3-001"],
        week_parity=WeekParity.ODD,
    )
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="B3-EVEN-WHOLE",
        teacher_ids=["teacher-b3-001"],
        week_parity=WeekParity.EVEN,
    )
    await db_session.commit()

    body = await _get_timetable(teacher_client, "teacher-b3-001", semester=semester)

    assert body["data"]["week"] is None
    assert [entry["course_id"] for entry in body["data"]["entries"]] == [
        "B3-ODD-WHOLE",
        "B3-EVEN-WHOLE",
    ]


async def test_filters_by_semester_and_teacher_membership(
    db_session: AsyncSession,
    teacher_client: AsyncClient,
):
    target_semester = _semester()
    other_semester = _semester()
    target_task = await _seed_task(db_session, target_semester)
    other_task = await _seed_task(db_session, other_semester)
    await _add_entry(
        db_session,
        target_task,
        semester=target_semester,
        course_id="B3-TEAM-TEACH",
        teacher_ids=["other-teacher", "teacher-b3-001"],
    )
    await _add_entry(
        db_session,
        target_task,
        semester=target_semester,
        course_id="B3-NOT-MY-COURSE",
        teacher_ids=["other-teacher"],
    )
    await _add_entry(
        db_session,
        other_task,
        semester=other_semester,
        course_id="B3-OTHER-SEMESTER",
        teacher_ids=["teacher-b3-001"],
    )
    await db_session.commit()

    body = await _get_timetable(
        teacher_client,
        "teacher-b3-001",
        semester=target_semester,
    )

    assert [entry["course_id"] for entry in body["data"]["entries"]] == ["B3-TEAM-TEACH"]


async def test_empty_result_returns_empty_entries(teacher_client: AsyncClient):
    body = await _get_timetable(
        teacher_client,
        "teacher-b3-001",
        semester=_semester(),
    )

    assert body["code"] == 0
    assert body["data"]["entries"] == []


async def test_admin_can_query_any_teacher(
    db_session: AsyncSession,
    admin_client: AsyncClient,
):
    semester = _semester()
    task = await _seed_task(db_session, semester)
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="B3-ADMIN-VIEW",
        teacher_ids=["teacher-b3-002"],
    )
    await db_session.commit()

    body = await _get_timetable(admin_client, "teacher-b3-002", semester=semester)

    assert body["code"] == 0
    assert [entry["course_id"] for entry in body["data"]["entries"]] == ["B3-ADMIN-VIEW"]


async def test_teacher_cannot_query_other_teacher(
    other_teacher_client: AsyncClient,
):
    body = await _get_timetable(
        other_teacher_client,
        "teacher-b3-001",
        semester=_semester(),
    )

    assert body["code"] == 2003


async def test_student_cannot_query_timetable(student_client: AsyncClient):
    body = await _get_timetable(
        student_client,
        "teacher-b3-001",
        semester=_semester(),
    )

    assert body["code"] == 2003


async def test_golden_all_parity_expands_across_weeks(
    db_session: AsyncSession,
    teacher_client: AsyncClient,
):
    """Golden: 一个 ALL 条目应在任意请求周中出现（这里检验周 1 和周 2）。"""
    semester = _semester()
    task = await _seed_task(db_session, semester)
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="G-ALL",
        teacher_ids=["teacher-b3-001"],
        week_start=1,
        week_end=2,
        week_parity=WeekParity.ALL,
    )
    await db_session.commit()

    body_w1 = await _get_timetable(teacher_client, "teacher-b3-001", semester=semester, week=1)
    body_w2 = await _get_timetable(teacher_client, "teacher-b3-001", semester=semester, week=2)

    assert [e["course_id"] for e in body_w1["data"]["entries"]] == ["G-ALL"]
    assert [e["course_id"] for e in body_w2["data"]["entries"]] == ["G-ALL"]


async def test_golden_odd_parity_only_shows_on_odd_week(
    db_session: AsyncSession,
    teacher_client: AsyncClient,
):
    semester = _semester()
    task = await _seed_task(db_session, semester)
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="G-ODD",
        teacher_ids=["teacher-b3-001"],
        week_start=1,
        week_end=3,
        week_parity=WeekParity.ODD,
    )
    await db_session.commit()

    odd_body = await _get_timetable(teacher_client, "teacher-b3-001", semester=semester, week=1)
    even_body = await _get_timetable(teacher_client, "teacher-b3-001", semester=semester, week=2)

    assert [e["course_id"] for e in odd_body["data"]["entries"]] == ["G-ODD"]
    assert even_body["data"]["entries"] == []


async def test_golden_even_parity_only_shows_on_even_week(
    db_session: AsyncSession,
    teacher_client: AsyncClient,
):
    semester = _semester()
    task = await _seed_task(db_session, semester)
    await _add_entry(
        db_session,
        task,
        semester=semester,
        course_id="G-EVEN",
        teacher_ids=["teacher-b3-001"],
        week_start=2,
        week_end=4,
        week_parity=WeekParity.EVEN,
    )
    await db_session.commit()

    odd_body = await _get_timetable(teacher_client, "teacher-b3-001", semester=semester, week=3)
    even_body = await _get_timetable(teacher_client, "teacher-b3-001", semester=semester, week=4)

    assert odd_body["data"]["entries"] == []
    assert [e["course_id"] for e in even_body["data"]["entries"]] == ["G-EVEN"]
