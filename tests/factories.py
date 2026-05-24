"""
tests/factories.py
算法层 dataclass 的构造工厂。纯函数实现，不引入 factory-boy 依赖。

用法示例：
    from tests.factories import make_course, make_classroom, make_minimal_solver_input

    courses, classrooms, preferences = make_minimal_solver_input()
    results, unscheduled = run_schedule(courses, classrooms, preferences)
"""

from app.algorithm.engine import (
    ClassroomInput,
    CourseInput,
    RoomRequirement,
    RoomType,
    TeacherPreference,
)


def make_course(**overrides) -> CourseInput:
    """构造一个 CourseInput，默认值可覆写。"""
    defaults = dict(
        course_id="C001",
        teacher_ids=["T001"],
        student_count=30,
        room_requirements=[RoomRequirement(RoomType.LECTURE, 2)],
    )
    defaults.update(overrides)
    return CourseInput(**defaults)


def make_classroom(**overrides) -> ClassroomInput:
    """构造一个 ClassroomInput，默认带 5×12 全可用时段。"""
    defaults = dict(
        classroom_id=1,
        campus="玉泉",
        capacity=60,
        room_type=RoomType.LECTURE,
        available_slots={(d, s) for d in range(1, 6) for s in range(1, 13)},
    )
    defaults.update(overrides)
    return ClassroomInput(**defaults)


def make_preference(**overrides) -> TeacherPreference:
    """构造一个 TeacherPreference，仅 teacher_id/semester 必填。"""
    defaults = dict(
        teacher_id="T001",
        semester="2024-2025-1",
        is_negative=False,
    )
    defaults.update(overrides)
    return TeacherPreference(**defaults)


def make_pref_payload(**overrides) -> dict:
    """构造一个 HTTP 表单/JSON payload，符合 TeacherPreferenceCreate 的字段。

    便于 e2e 测试直接 POST 到 /api/v1/teacher-preferences。
    """
    defaults = dict(
        semester="2024-2025-1",
        course_id=None,
        campus="玉泉",
        building="教三",
        classroom_code=None,
        room_type="LECTURE",
        day_of_week=1,
        slot_start=1,
        slot_end=2,
        week_start=1,
        week_end=16,
        week_parity="ALL",
        is_negative=False,
    )
    defaults.update(overrides)
    return defaults


def make_minimal_solver_input() -> tuple[
    list[CourseInput], list[ClassroomInput], list[TeacherPreference]
]:
    """4 课 / 2 教室 / 0 偏好的最小可解输入，用于 smoke 级 solver 测试。
    C004 是混合课（讲授 + 实验），用于验证 room_requirements 多项能力。"""
    courses = [
        make_course(course_id="C001", teacher_ids=["T001"], student_count=30),
        make_course(course_id="C002", teacher_ids=["T002"], student_count=50),
        make_course(
            course_id="C003",
            teacher_ids=["T003"],
            student_count=20,
            room_requirements=[RoomRequirement(RoomType.LAB_CHEMISTRY, 2)],
        ),
        make_course(
            course_id="C004",
            teacher_ids=["T004"],
            student_count=40,
            room_requirements=[
                RoomRequirement(RoomType.LECTURE, 2),
                RoomRequirement(RoomType.LAB_CHEMISTRY, 2),
            ],
        ),
    ]
    classrooms = [
        make_classroom(classroom_id=1, capacity=60, room_type=RoomType.LECTURE),
        make_classroom(classroom_id=2, capacity=80, room_type=RoomType.LAB_CHEMISTRY),
    ]
    preferences: list[TeacherPreference] = []
    return courses, classrooms, preferences
