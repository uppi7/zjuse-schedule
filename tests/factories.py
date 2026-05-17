"""
tests/factories.py
算法层 dataclass 的构造工厂。纯函数实现，不引入 factory-boy 依赖。

用法示例：
    from tests.factories import make_course, make_classroom, make_minimal_solver_input

    courses, classrooms, preferences = make_minimal_solver_input()
    results, unscheduled = run_schedule(courses, classrooms, preferences)
"""

from app.algorithm.engine import (
    CourseInput,
    ClassroomInput,
    TeacherPreference,
)


def make_course(**overrides) -> CourseInput:
    """构造一个 CourseInput，默认值可覆写。"""
    defaults = dict(
        course_id="C001",
        teacher_ids=["T001"],
        student_count=30,
        weekly_hours=2,
        needs_lab=False,
    )
    defaults.update(overrides)
    return CourseInput(**defaults)


def make_classroom(**overrides) -> ClassroomInput:
    """构造一个 ClassroomInput，默认带 5×12 全可用时段。"""
    defaults = dict(
        classroom_id=1,
        campus="玉泉",
        capacity=60,
        is_lab=False,
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


def make_minimal_solver_input() -> tuple[
    list[CourseInput], list[ClassroomInput], list[TeacherPreference]
]:
    """3 课 / 2 教室 / 0 偏好的最小可解输入，用于 smoke 级 solver 测试。"""
    courses = [
        make_course(course_id="C001", teacher_ids=["T001"], student_count=30),
        make_course(course_id="C002", teacher_ids=["T002"], student_count=50),
        make_course(course_id="C003", teacher_ids=["T003"], student_count=20, needs_lab=True),
    ]
    classrooms = [
        make_classroom(classroom_id=1, capacity=60, is_lab=False),
        make_classroom(classroom_id=2, capacity=80, is_lab=True),
    ]
    preferences: list[TeacherPreference] = []
    return courses, classrooms, preferences
