"""
tests/solver/conftest.py
Solver 层 golden case 加载/对比 helper

Golden case 目录结构：
    tests/solver/fixtures/golden/<case_name>/
        input.json      # SolverInput 序列化：{courses, classrooms, preferences}
        expected.json   # SolverExpected 序列化：见下方 dataclass

input.json 字段对应 app/algorithm/engine.py 中的 dataclass：
    courses     : list[CourseInput]
                  room_requirements 用 [{"room_type": <RoomType 取值>, "hours": int}, ...]
    classrooms  : list[ClassroomInput]    # available_slots 用 [[d, s], ...] 表示
                  room_type 取值见 RoomType 枚举（LECTURE / LAB_* / COMPUTER_LAB / GYM）
    preferences : list[TeacherPreference]

expected.json 字段（断言对照）：
    scheduled_count   : int       # 期望成功排课数
    unscheduled_ids   : list[str] # 期望未能排课的 course_id 集合
    max_conflicts     : int = 0   # 允许的硬冲突数上限（教师/教室时间冲突）
    extra             : dict      # 额外断言（如教师工作量上限等），由 tester 扩展
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.algorithm.engine import (
    CourseInput,
    ClassroomInput,
    TeacherPreference,
    ScheduleResult,
    RoomRequirement,
    RoomType,
)

GOLDEN_ROOT = Path(__file__).parent / "fixtures" / "golden"


@dataclass
class SolverInput:
    courses: list[CourseInput]
    classrooms: list[ClassroomInput]
    preferences: list[TeacherPreference]


@dataclass
class SolverExpected:
    scheduled_count: int
    unscheduled_ids: list[str] = field(default_factory=list)
    max_conflicts: int = 0
    extra: dict = field(default_factory=dict)


def discover_golden_cases() -> list[Path]:
    """枚举 fixtures/golden/ 下所有 case 目录（跳过下划线开头的占位/草稿）。"""
    if not GOLDEN_ROOT.exists():
        return []
    return sorted(
        p for p in GOLDEN_ROOT.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    )


def load_golden_case(case_dir: Path) -> tuple[SolverInput, SolverExpected]:
    """读取 case_dir/{input.json, expected.json} 并反序列化为 dataclass。"""
    input_path = case_dir / "input.json"
    expected_path = case_dir / "expected.json"

    raw_input = json.loads(input_path.read_text(encoding="utf-8"))
    raw_expected = json.loads(expected_path.read_text(encoding="utf-8"))

    courses = [
        CourseInput(
            course_id=c["course_id"],
            teacher_ids=c["teacher_ids"],
            student_count=c["student_count"],
            room_requirements=[
                RoomRequirement(RoomType(r["room_type"]), r["hours"])
                for r in c.get("room_requirements", [])
            ],
        )
        for c in raw_input.get("courses", [])
    ]
    classrooms = [
        ClassroomInput(
            classroom_id=c["classroom_id"],
            campus=c["campus"],
            capacity=c["capacity"],
            room_type=RoomType(c.get("room_type", "LECTURE")),
            available_slots={tuple(s) for s in c.get("available_slots", [])},
        )
        for c in raw_input.get("classrooms", [])
    ]
    preferences = [TeacherPreference(**p) for p in raw_input.get("preferences", [])]

    return (
        SolverInput(courses=courses, classrooms=classrooms, preferences=preferences),
        SolverExpected(**raw_expected),
    )


def count_hard_conflicts(results: list[ScheduleResult]) -> int:
    """
    统计硬冲突数：同教师同时段 / 同教室同时段。

    粗粒度实现：按 (day, slot) 展开为分钟级时间点，统计教师/教室占用次数 > 1 的次数
    更精细的统计（含 week_parity / week_start-end）由 tester 在真算法落地后扩展
    """
    teacher_slots: dict[tuple[str, int, int], int] = {}
    room_slots: dict[tuple[int, int, int], int] = {}

    for r in results:
        for slot in range(r.slot_start, r.slot_end + 1):
            for t in r.teacher_ids:
                key_t = (t, r.day_of_week, slot)
                teacher_slots[key_t] = teacher_slots.get(key_t, 0) + 1
            key_r = (r.classroom_id, r.day_of_week, slot)
            room_slots[key_r] = room_slots.get(key_r, 0) + 1

    conflicts = sum(max(0, v - 1) for v in teacher_slots.values())
    conflicts += sum(max(0, v - 1) for v in room_slots.values())
    return conflicts


def assert_solver_result(
    results: list[ScheduleResult],
    unscheduled: list[str],
    expected: SolverExpected,
) -> None:
    """
    基础断言。tester 可在 test 函数里追加 case 特定断言（如教师工作量上限、
    跨校区相邻禁忌等）。
    """
    assert len(results) == expected.scheduled_count, (
        f"scheduled count mismatch: got {len(results)}, expected {expected.scheduled_count}"
    )
    assert set(unscheduled) == set(expected.unscheduled_ids), (
        f"unscheduled set mismatch: got {sorted(unscheduled)}, "
        f"expected {sorted(expected.unscheduled_ids)}"
    )
    conflicts = count_hard_conflicts(results)
    assert conflicts <= expected.max_conflicts, (
        f"hard conflicts {conflicts} exceeds limit {expected.max_conflicts}"
    )
