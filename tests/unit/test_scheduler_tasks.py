"""
tests/unit/test_scheduler_tasks.py
排课异步任务的输入映射、状态机和结果落库单元测试。
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.algorithm.engine import RoomType, ScheduleResult
from app.models.classroom import Classroom, ClassroomType
from app.models.schedule import DayOfWeek, ScheduleEntry, ScheduleStatus, ScheduleTask, WeekParity
from app.schemas.response import BizCode, BizException
from app.schemas.schedule import AutoScheduleRequest
from app.services import schedule_service
from app.tasks import scheduler_tasks

pytestmark = pytest.mark.unit


def test_map_course_payload_to_algorithm_input():
    course = scheduler_tasks._map_course(
        {
            "course_id": "C001",
            "teacher_id": "T001",
            "student_count": "45",
            "room_requirements": [
                {"room_type": "LECTURE", "hours": 2},
                {"room_type": "COMPUTER_LAB", "hours": "0"},
            ],
        }
    )

    assert course.course_id == "C001"
    assert course.teacher_ids == ["T001"]
    assert course.student_count == 45
    assert len(course.room_requirements) == 1
    assert course.room_requirements[0].room_type == RoomType.LECTURE
    assert course.room_requirements[0].hours == 2


def test_invalid_course_payload_raises_upstream_error():
    with pytest.raises(BizException) as exc_info:
        scheduler_tasks._map_courses([{"course_id": "BROKEN"}])

    assert exc_info.value.code == BizCode.UPSTREAM_FETCH_FAILED


async def test_fetch_course_payloads_uses_stub_when_enabled(monkeypatch):
    class FailingInfoServiceClient:
        def __init__(self, user_id: str, role: str) -> None:
            self.user_id = user_id
            self.role = role
            self.closed = False

        async def get_all_courses(self, semester: str):
            raise RuntimeError("upstream down")

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setattr(scheduler_tasks, "InfoServiceClient", FailingInfoServiceClient)
    monkeypatch.setattr(
        scheduler_tasks.settings,
        "ALLOW_UPSTREAM_STUB_FALLBACK",
        True,
    )

    rows = await scheduler_tasks._fetch_course_payloads("2024-2025-1", "admin-001")

    assert rows[0]["course_id"] == "STUB-C001"
    assert rows[0]["semester"] == "2024-2025-1"


async def test_fetch_course_payloads_fails_when_stub_disabled(monkeypatch):
    class FailingInfoServiceClient:
        def __init__(self, user_id: str, role: str) -> None:
            pass

        async def get_all_courses(self, semester: str):
            raise RuntimeError("upstream down")

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(scheduler_tasks, "InfoServiceClient", FailingInfoServiceClient)
    monkeypatch.setattr(
        scheduler_tasks.settings,
        "ALLOW_UPSTREAM_STUB_FALLBACK",
        False,
    )

    with pytest.raises(BizException) as exc_info:
        await scheduler_tasks._fetch_course_payloads("2024-2025-1", "admin-001")

    assert exc_info.value.code == BizCode.UPSTREAM_FETCH_FAILED


async def test_fetch_upstream_data_maps_classrooms_and_preferences(
    db_session: AsyncSession,
    monkeypatch,
):
    async def fake_fetch_course_payloads(semester: str, triggered_by: str):
        return [
            {
                "course_id": "C001",
                "teacher_id": "T001",
                "student_count": 30,
                "room_requirements": [{"room_type": "LECTURE", "hours": 2}],
            }
        ]

    async def fake_list_for_algorithm(db: AsyncSession, semester: str):
        return []

    db_session.add(
        Classroom(
            code="B1-ROOM-1",
            name="B1 Test Room",
            campus="玉泉",
            building="测试楼",
            capacity=60,
            room_type=ClassroomType.LECTURE,
            available_time=[{"day": 1, "slot": 1}, {"day": 1, "slot": 2}],
            is_active=True,
        )
    )
    await db_session.commit()

    monkeypatch.setattr(
        scheduler_tasks,
        "AsyncSessionLocal",
        lambda: _SessionContext(db_session),
    )
    monkeypatch.setattr(scheduler_tasks, "_fetch_course_payloads", fake_fetch_course_payloads)
    monkeypatch.setattr(
        scheduler_tasks.teacher_preference_service,
        "list_for_algorithm",
        fake_list_for_algorithm,
    )

    courses, classrooms, preferences = await scheduler_tasks._fetch_upstream_data(
        "2024-2025-1",
        "admin-001",
    )

    assert courses[0].course_id == "C001"
    assert classrooms[0].room_type == RoomType.LECTURE
    assert classrooms[0].available_slots == {(1, 1), (1, 2)}
    assert preferences == []


async def test_save_results_writes_entries_and_success_status(
    db_session: AsyncSession,
    monkeypatch,
):
    task = ScheduleTask(
        celery_task_id="celery-success",
        semester="2024-2025-1",
        status=ScheduleStatus.RUNNING,
        triggered_by="admin-001",
    )
    db_session.add(task)
    await db_session.commit()

    monkeypatch.setattr(
        scheduler_tasks,
        "AsyncSessionLocal",
        lambda: _SessionContext(db_session),
    )

    await scheduler_tasks._save_results(
        "celery-success",
        "2024-2025-1",
        [
            ScheduleResult(
                course_id="C001",
                teacher_ids=["T001"],
                classroom_id=1,
                day_of_week=1,
                slot_start=1,
                slot_end=2,
            )
        ],
        [],
    )

    await db_session.refresh(task)
    entries = (
        (await db_session.execute(select(ScheduleEntry).where(ScheduleEntry.task_id == task.id)))
        .scalars()
        .all()
    )

    assert task.status == ScheduleStatus.SUCCESS
    assert task.result_meta == {"unscheduled": [], "unscheduled_count": 0}
    assert len(entries) == 1
    assert entries[0].course_id == "C001"
    assert entries[0].teacher_ids == ["T001"]


async def test_save_results_is_idempotent_and_marks_partial(
    db_session: AsyncSession,
    monkeypatch,
):
    task = ScheduleTask(
        celery_task_id="celery-partial",
        semester="2024-2025-1",
        status=ScheduleStatus.RUNNING,
        triggered_by="admin-001",
    )
    db_session.add(task)
    await db_session.flush()
    db_session.add(
        ScheduleEntry(
            task_id=task.id,
            semester="2024-2025-1",
            course_id="OLD",
            teacher_ids=["OLD-T"],
            classroom_id=1,
            day_of_week=DayOfWeek.MON,
            slot_start=1,
            slot_end=2,
            week_start=1,
            week_end=16,
            week_parity=WeekParity.ALL,
        )
    )
    await db_session.commit()

    monkeypatch.setattr(
        scheduler_tasks,
        "AsyncSessionLocal",
        lambda: _SessionContext(db_session),
    )

    await scheduler_tasks._save_results(
        "celery-partial",
        "2024-2025-1",
        [
            ScheduleResult(
                course_id="NEW",
                teacher_ids=["T002"],
                classroom_id=2,
                day_of_week=2,
                slot_start=3,
                slot_end=4,
            )
        ],
        ["UNSCHEDULED-C001"],
    )

    await db_session.refresh(task)
    entries = (
        (await db_session.execute(select(ScheduleEntry).where(ScheduleEntry.task_id == task.id)))
        .scalars()
        .all()
    )

    assert task.status == ScheduleStatus.PARTIAL
    assert task.result_meta == {
        "unscheduled": ["UNSCHEDULED-C001"],
        "unscheduled_count": 1,
    }
    assert [entry.course_id for entry in entries] == ["NEW"]


async def test_mark_task_failed_writes_error_message(
    db_session: AsyncSession,
    monkeypatch,
):
    task = ScheduleTask(
        celery_task_id="celery-failed",
        semester="2024-2025-1",
        status=ScheduleStatus.RUNNING,
        triggered_by="admin-001",
    )
    db_session.add(task)
    await db_session.commit()

    monkeypatch.setattr(
        scheduler_tasks,
        "AsyncSessionLocal",
        lambda: _SessionContext(db_session),
    )

    await scheduler_tasks._mark_task_failed(
        "celery-failed",
        BizException(BizCode.ALGORITHM_NO_SOLUTION, "no solution"),
    )

    await db_session.refresh(task)
    assert task.status == ScheduleStatus.FAILED
    assert task.error_msg == "2099: no solution"


async def test_trigger_auto_schedule_creates_task_before_enqueue(
    db_session: AsyncSession,
    monkeypatch,
):
    captured = {}

    def fake_apply_async(args, task_id):
        captured["args"] = args
        captured["task_id"] = task_id
        return object()

    monkeypatch.setattr(
        schedule_service.scheduler_tasks.run_auto_schedule,
        "apply_async",
        fake_apply_async,
    )

    task_id, semester = await schedule_service.trigger_auto_schedule(
        db_session,
        AutoScheduleRequest(semester="2024-2025-1"),
        "admin-001",
    )

    task = await db_session.scalar(
        select(ScheduleTask).where(ScheduleTask.celery_task_id == task_id)
    )

    assert semester == "2024-2025-1"
    assert task is not None
    assert task.status == ScheduleStatus.PENDING
    assert captured == {
        "args": ("2024-2025-1", "admin-001"),
        "task_id": task_id,
    }


async def test_manual_adjust_updates_entry_and_persists(
    client,
    db_session: AsyncSession,
):
    semester = "2024-2025-1"
    task = ScheduleTask(
        celery_task_id="celery-manual-adjust",
        semester=semester,
        status=ScheduleStatus.SUCCESS,
        triggered_by="admin-001",
    )
    source_classroom = Classroom(
        code="MANUAL-SRC",
        name="原教室",
        campus="玉泉",
        building="教三",
        capacity=80,
        room_type=ClassroomType.LECTURE,
        available_time=[],
        is_active=True,
    )
    target_classroom = Classroom(
        code="MANUAL-TGT",
        name="目标教室",
        campus="紫金港",
        building="西教",
        capacity=120,
        room_type=ClassroomType.LECTURE,
        available_time=[],
        is_active=True,
    )
    db_session.add_all([task, source_classroom, target_classroom])
    await db_session.flush()

    entry = ScheduleEntry(
        task_id=task.id,
        semester=semester,
        course_id="MANUAL-C001",
        teacher_ids=["teacher-manual-001"],
        classroom_id=source_classroom.id,
        day_of_week=DayOfWeek.MON,
        slot_start=1,
        slot_end=2,
        week_start=1,
        week_end=16,
        week_parity=WeekParity.ALL,
    )
    db_session.add(entry)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/schedule/manual-adjust",
        json={
            "entry_id": entry.id,
            "new_classroom_id": target_classroom.id,
            "new_teacher_ids": ["teacher-manual-002"],
            "new_day_of_week": 5,
            "new_slot_start": 3,
            "new_slot_end": 4,
            "new_week_start": 2,
            "new_week_end": 8,
            "new_week_parity": "EVEN",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["classroom_id"] == target_classroom.id
    assert body["data"]["teacher_ids"] == ["teacher-manual-002"]
    assert body["data"]["day_of_week"] == 5
    assert body["data"]["slot_start"] == 3
    assert body["data"]["slot_end"] == 4
    assert body["data"]["week_start"] == 2
    assert body["data"]["week_end"] == 8
    assert body["data"]["week_parity"] == "EVEN"

    await db_session.refresh(entry)
    assert entry.classroom_id == target_classroom.id
    assert entry.teacher_ids == ["teacher-manual-002"]
    assert entry.day_of_week == DayOfWeek.FRI
    assert entry.slot_start == 3
    assert entry.slot_end == 4
    assert entry.week_start == 2
    assert entry.week_end == 8
    assert entry.week_parity == WeekParity.EVEN


class _SessionContext:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        await self._session.rollback()
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            await self._session.rollback()
