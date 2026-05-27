"""
tests/solver/test_solver_golden.py
排课算法回归测试。

职责分层：
  Part 1  fixture-based golden cases  — 参数化读 fixtures/golden/*，conftest 加载+断言
  Part 2  硬约束 unit tests           — 每个硬约束（H1-H5）独立一个函数，输入最小、断言精确
  Part 3  混合课 / room_requirements  — 多项需求合并、hours==0 忽略、重复类型合并
  Part 4  软约束 smoke tests          — 负偏好不导致 unscheduled；正偏好驱动排课倾向
  Part 5  smoke & 覆盖性检查          — 最小输入、空输入等边界
  Part 6  性能基线                    — 小/中规模限时断言

运行：
  make test-solver
  pytest tests/solver/ -m solver -v
"""

import time
import pytest

from app.algorithm.engine import (
    ClassroomInput,
    CourseInput,
    RoomRequirement,
    RoomType,
    ScheduleResult,
    TeacherPreference,
    run_schedule,
)
from tests.factories import (
    make_course,
    make_classroom,
    make_preference,
    # make_slots,
    make_minimal_solver_input,
)
from tests.solver.conftest import (
    assert_solver_result,
    discover_golden_cases,
    load_golden_case,
)

pytestmark = pytest.mark.solver


# ══════════════════════════════════════════════════════════════════
# 通用断言辅助（本文件内共用，不放 conftest 以保持 conftest 职责单一）
# ══════════════════════════════════════════════════════════════════

def _assert_hard_constraints(
    results: list[ScheduleResult],
    courses: list[CourseInput],
    classrooms: list[ClassroomInput],
) -> None:
    """
    全量硬约束检查：值域合法性 + H1-H5。
    任何违反都以 AssertionError 明确说明约束编号与上下文。
    """
    cls_map = {c.classroom_id: c for c in classrooms}
    course_map = {c.course_id: c for c in courses}

    # 值域合法性
    for r in results:
        assert 1 <= r.day_of_week <= 7, \
            f"[值域] {r.course_id}: day_of_week={r.day_of_week} 不在 [1,7]"
        assert 1 <= r.slot_start <= 12, \
            f"[值域] {r.course_id}: slot_start={r.slot_start} 不在 [1,12]"
        assert 1 <= r.slot_end <= 12, \
            f"[值域] {r.course_id}: slot_end={r.slot_end} 不在 [1,12]"
        assert r.slot_start <= r.slot_end, \
            f"[值域] {r.course_id}: slot_start={r.slot_start} > slot_end={r.slot_end}"
        assert 1 <= r.week_start <= 16, \
            f"[值域] {r.course_id}: week_start={r.week_start} 不在 [1,16]"
        assert 1 <= r.week_end <= 16, \
            f"[值域] {r.course_id}: week_end={r.week_end} 不在 [1,16]"
        assert r.week_start <= r.week_end, \
            f"[值域] {r.course_id}: week_start={r.week_start} > week_end={r.week_end}"
        assert r.week_parity in {"ALL", "ODD", "EVEN"}, \
            f"[值域] {r.course_id}: week_parity={r.week_parity!r} 不合法"

    # H1：同一教师同一时段不能有两门课
    teacher_used: dict[str, set[tuple[int, int]]] = {}
    for r in results:
        for tid in r.teacher_ids:
            used = teacher_used.setdefault(tid, set())
            for s in range(r.slot_start, r.slot_end + 1):
                key = (r.day_of_week, s)
                assert key not in used, (
                    f"[H1] 教师 {tid} 在 day={r.day_of_week} slot={s} 已有课，"
                    f"course={r.course_id} 冲突"
                )
                used.add(key)

    # H2：同一教室同一时段不能有两门课
    room_used: dict[int, set[tuple[int, int]]] = {}
    for r in results:
        used = room_used.setdefault(r.classroom_id, set())
        for s in range(r.slot_start, r.slot_end + 1):
            key = (r.day_of_week, s)
            assert key not in used, (
                f"[H2] 教室 {r.classroom_id} 在 day={r.day_of_week} slot={s} 已被占用，"
                f"course={r.course_id} 冲突"
            )
            used.add(key)

    # H3：教室容量 >= 课程学生数
    for r in results:
        course = course_map.get(r.course_id)
        room = cls_map.get(r.classroom_id)
        if course and room:
            assert room.capacity >= course.student_count, (
                f"[H3] 教室 {r.classroom_id} 容量 {room.capacity} "
                f"< 课程 {r.course_id} 学生数 {course.student_count}"
            )

    # H4：教室类型必须出现在课程 room_requirements 中
    for r in results:
        course = course_map.get(r.course_id)
        room = cls_map.get(r.classroom_id)
        if course and room:
            req_types = {req.room_type for req in course.room_requirements if req.hours > 0}
            assert room.room_type in req_types, (
                f"[H4] 课程 {r.course_id} 的教室类型 {room.room_type.value} "
                f"不在需求 {[t.value for t in req_types]} 中"
            )

    # H5：时段必须落在教室 available_slots 内
    for r in results:
        room = cls_map.get(r.classroom_id)
        if room:
            for s in range(r.slot_start, r.slot_end + 1):
                assert (r.day_of_week, s) in room.available_slots, (
                    f"[H5] 教室 {r.classroom_id} 在 day={r.day_of_week} slot={s} "
                    f"不在 available_slots 内，course={r.course_id}"
                )


def _assert_coverage(
    results: list[ScheduleResult],
    unscheduled: list[str],
    courses: list[CourseInput],
) -> None:
    """每门课要么出现在 results（通过 course_id），要么在 unscheduled，二者不重叠。"""
    scheduled_ids = {r.course_id for r in results}
    unscheduled_ids = set(unscheduled)
    all_ids = {c.course_id for c in courses}

    assert scheduled_ids & unscheduled_ids == set(), (
        f"course_id 同时出现在 results 和 unscheduled: {scheduled_ids & unscheduled_ids}"
    )
    assert scheduled_ids | unscheduled_ids == all_ids, (
        f"存在既未排课也未进 unscheduled 的课程: {all_ids - scheduled_ids - unscheduled_ids}"
    )


# ══════════════════════════════════════════════════════════════════
# Part 1：fixture-based golden cases（conftest 驱动）
# ══════════════════════════════════════════════════════════════════

GOLDEN_CASES = discover_golden_cases()


@pytest.mark.parametrize(
    "case_dir",
    GOLDEN_CASES,
    ids=[p.name for p in GOLDEN_CASES] if GOLDEN_CASES else ["no-cases"],
)
def test_solver_golden_case(case_dir):
    """
    参数化 golden case 回归：对 fixtures/golden/* 每个目录跑一次，
    用 conftest.assert_solver_result 对照 expected.json。
    """
    if not GOLDEN_CASES:
        pytest.skip("尚无 golden case：在 tests/solver/fixtures/golden/ 下添加 case 目录")

    solver_input, expected = load_golden_case(case_dir)
    results, unscheduled = run_schedule(
        solver_input.courses,
        solver_input.classrooms,
        solver_input.preferences,
    )

    # conftest 基础断言（scheduled_count / unscheduled_ids / max_conflicts）
    assert_solver_result(results, unscheduled, expected)

    # 追加：全量硬约束 + 覆盖性检查（conftest 只计 conflict 数，这里逐条定位）
    _assert_hard_constraints(results, solver_input.courses, solver_input.classrooms)
    _assert_coverage(results, unscheduled, solver_input.courses)


# ══════════════════════════════════════════════════════════════════
# Part 2：硬约束 unit tests（每个约束独立覆盖）
# ══════════════════════════════════════════════════════════════════

def test_h1_teacher_conflict_avoided():
    """H1：同一教师教两门课，必须排到不同时段，无冲突。"""
    courses = [
        make_course(course_id="C001", teacher_ids=["T001"]),
        make_course(course_id="C002", teacher_ids=["T001"]),
    ]
    classrooms = [
        make_classroom(classroom_id=1),
        make_classroom(classroom_id=2),
    ]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert not unscheduled, f"两门课都应排上，unscheduled={unscheduled}"
    _assert_hard_constraints(results, courses, classrooms)


def test_h1_teacher_conflict_causes_unscheduled():
    """H1 极端场景：只有1个时段，同一教师3门课 → 最多排1门，其余进 unscheduled。"""
    courses = [
        make_course(course_id="C001", teacher_ids=["T001"], student_count=10),
        make_course(course_id="C002", teacher_ids=["T001"], student_count=10),
        make_course(course_id="C003", teacher_ids=["T001"], student_count=10),
    ]
    classrooms = [
        make_classroom(classroom_id=1, available_slots={(1, 1), (1, 2)}),
    ]
    results, unscheduled = run_schedule(courses, classrooms, [])

    _assert_coverage(results, unscheduled, courses)
    _assert_hard_constraints(results, courses, classrooms)
    assert len({r.course_id for r in results}) <= 1, "同一时段同一教师最多排1门课"
    assert len(unscheduled) >= 2, "剩余至少2门进 unscheduled"


def test_h2_classroom_conflict_avoided():
    """H2：同一教室同一时段不能排两门课，算法必须分开到不同时段。"""
    courses = [
        make_course(course_id="C001", teacher_ids=["T001"]),
        make_course(course_id="C002", teacher_ids=["T002"]),
    ]
    classrooms = [make_classroom(classroom_id=1)]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert not unscheduled, f"教室时段充足，两门课都应排上，unscheduled={unscheduled}"
    _assert_hard_constraints(results, courses, classrooms)


def test_h3_capacity_insufficient_causes_unscheduled():
    """H3：学生数超过所有同类型教室容量 → 该课进 unscheduled，其他课不受影响。"""
    courses = [
        make_course(course_id="C001", student_count=30),
        make_course(course_id="C_BIG", teacher_ids=["T999"], student_count=200),
    ]
    classrooms = [make_classroom(classroom_id=1, capacity=60)]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert "C_BIG" in unscheduled, "超容量课应进 unscheduled"
    assert "C001" not in unscheduled, "正常课不应受超容量课影响"
    _assert_hard_constraints(results, courses, classrooms)


def test_h4_room_type_mismatch_causes_unscheduled():
    """H4：课程需要 LAB_PHYSICS，但无此类型教室 → 进 unscheduled。"""
    courses = [
        make_course(
            course_id="C001",
            room_requirements=[RoomRequirement(RoomType.LAB_PHYSICS, 2)],
        )
    ]
    classrooms = [make_classroom(classroom_id=1, room_type=RoomType.LECTURE)]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert "C001" in unscheduled, "无匹配房型时应进 unscheduled"
    assert results == []


def test_h5_available_slots_respected():
    """H5：排课结果必须落在教室 available_slots 内。"""
    limited = {(3, 5), (3, 6)}  # 只有周三 5-6 节
    courses = [make_course(course_id="C001", student_count=20)]
    classrooms = [make_classroom(classroom_id=1, available_slots=limited)]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert not unscheduled, "有合法时段时应排上"
    assert len(results) == 1
    r = results[0]
    assert r.day_of_week == 3 and r.slot_start == 5 and r.slot_end == 6, (
        f"结果应落在唯一可用时段 day=3 5-6，实际 day={r.day_of_week} {r.slot_start}-{r.slot_end}"
    )
    _assert_hard_constraints(results, courses, classrooms)


def test_h5_no_available_slot_causes_unscheduled():
    """H5 边界：available_slots 为空 → 课程无法排入，进 unscheduled。"""
    courses = [make_course(course_id="C001")]
    classrooms = [make_classroom(classroom_id=1, available_slots=set())]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert "C001" in unscheduled, "无可用时段时应进 unscheduled"
    assert results == []


def test_h5_discontiguous_slots_cause_unscheduled():
    """H5 边界：孤立的单节时段凑不出连续2节 → 2节课进 unscheduled。"""
    isolated = {(1, 1), (1, 3), (1, 5)}  # 相邻节均不连续
    courses = [
        make_course(
            course_id="C001",
            room_requirements=[RoomRequirement(RoomType.LECTURE, 2)],
        )
    ]
    classrooms = [make_classroom(classroom_id=1, available_slots=isolated)]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert "C001" in unscheduled, "孤立时段无法构成连续2节，应进 unscheduled"


# ══════════════════════════════════════════════════════════════════
# Part 3：混合课 / room_requirements 边界
# ══════════════════════════════════════════════════════════════════

def test_mixed_course_produces_multiple_results():
    """混合课（LECTURE + LAB_CHEMISTRY）应产生2条 ScheduleResult，且各自房型正确。"""
    courses = [
        make_course(
            course_id="C001",
            teacher_ids=["T001"],
            student_count=40,
            room_requirements=[
                RoomRequirement(RoomType.LECTURE, 2),
                RoomRequirement(RoomType.LAB_CHEMISTRY, 2),
            ],
        )
    ]
    classrooms = [
        make_classroom(classroom_id=1, capacity=60, room_type=RoomType.LECTURE),
        make_classroom(classroom_id=2, capacity=60, room_type=RoomType.LAB_CHEMISTRY),
    ]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert not unscheduled, "混合课在教室充足时应全排上"
    assert len(results) == 2, f"混合课应产生2条记录，实际 {len(results)}"
    room_types_used = {
        next(c.room_type for c in classrooms if c.classroom_id == r.classroom_id)
        for r in results
    }
    assert room_types_used == {RoomType.LECTURE, RoomType.LAB_CHEMISTRY}, (
        "两条记录应分别使用 LECTURE 和 LAB_CHEMISTRY 教室"
    )
    _assert_hard_constraints(results, courses, classrooms)


def test_zero_hours_requirement_ignored():
    """hours==0 的 room_requirement 应被忽略，不影响排课结果。"""
    courses = [
        make_course(
            course_id="C001",
            room_requirements=[
                RoomRequirement(RoomType.LECTURE, 2),
                RoomRequirement(RoomType.LAB_PHYSICS, 0),  # 应忽略
            ],
        )
    ]
    # 故意不提供 LAB_PHYSICS 教室：若 hours=0 被正确忽略则不影响结果
    classrooms = [make_classroom(classroom_id=1, room_type=RoomType.LECTURE)]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert not unscheduled, "hours=0 的项应被忽略，课程应正常排上"
    _assert_hard_constraints(results, courses, classrooms)


def test_duplicate_room_type_requirements_merged():
    """同一 room_type 出现多次时按总学时合并，产生正确数量的 session。"""
    # LECTURE hours=2 + LECTURE hours=2 → 合并为 hours=4 → 2次课 → 2条记录
    courses = [
        make_course(
            course_id="C001",
            room_requirements=[
                RoomRequirement(RoomType.LECTURE, 2),
                RoomRequirement(RoomType.LECTURE, 2),
            ],
        )
    ]
    classrooms = [make_classroom(classroom_id=1, capacity=60)]
    results, unscheduled = run_schedule(courses, classrooms, [])

    assert not unscheduled
    assert len(results) == 2, (
        f"LECTURE hours=2+2 合并为4，应拆成2条记录，实际 {len(results)}"
    )
    _assert_hard_constraints(results, courses, classrooms)


# ══════════════════════════════════════════════════════════════════
# Part 4：软约束 smoke tests
# ══════════════════════════════════════════════════════════════════

def test_soft_positive_preference_no_crash():
    """正偏好：算法不崩溃，课程排上，无硬冲突。"""
    courses = [make_course(course_id="C001", teacher_ids=["T001"])]
    classrooms = [make_classroom(classroom_id=1)]
    prefs = [
        make_preference(teacher_id="T001", day_of_week=2, slot_start=1, slot_end=2),
    ]
    results, unscheduled = run_schedule(courses, classrooms, prefs)

    assert not unscheduled
    _assert_hard_constraints(results, courses, classrooms)


# def test_soft_negative_preference_does_not_cause_unscheduled():
#     """
#     负偏好（is_negative=True）是软扣分，不得导致 unscheduled。
#     即使唯一可用时段被标记为禁忌，课程也必须排上。
#     """
#     monday_only = make_slots(1)  # 只有周一可用
#     courses = [make_course(course_id="C001", teacher_ids=["T001"])]
#     classrooms = [make_classroom(classroom_id=1, available_slots=monday_only)]
#     prefs = [
#         make_preference(teacher_id="T001", day_of_week=1, is_negative=True),
#     ]
#     results, unscheduled = run_schedule(courses, classrooms, prefs)

#     assert not unscheduled, "负偏好为软约束，唯一可用时段仍须排课"
#     _assert_hard_constraints(results, courses, classrooms)


def test_soft_negative_preference_avoided_when_alternatives_exist():
    """
    负偏好存在替代时段时，算法应倾向避开禁忌天。
    教室全周可用，T001 标记周一为禁忌 → 结果应不在周一。
    """
    courses = [make_course(course_id="C001", teacher_ids=["T001"])]
    classrooms = [make_classroom(classroom_id=1)]  # 默认全周可用
    prefs = [
        make_preference(teacher_id="T001", day_of_week=1, is_negative=True),
    ]
    results, unscheduled = run_schedule(courses, classrooms, prefs)

    assert not unscheduled
    assert len(results) == 1
    assert results[0].day_of_week != 1, (
        f"替代时段充足时，负偏好应驱动排课避开周一，实际排在 day={results[0].day_of_week}"
    )
    _assert_hard_constraints(results, courses, classrooms)


# ══════════════════════════════════════════════════════════════════
# Part 5：smoke & 覆盖性检查
# ══════════════════════════════════════════════════════════════════

def test_minimal_input_does_not_crash():
    """
    smoke：最小输入不抛异常，每门课要么排上要么进 unscheduled，二者不重叠。
    注意：make_minimal_solver_input 含混合课 C004，results 条数为 5 而非 4，
    覆盖性断言使用 course_id 集合而非条数。
    """
    courses, classrooms, preferences = make_minimal_solver_input()
    results, unscheduled = run_schedule(courses, classrooms, preferences)

    assert isinstance(results, list)
    assert isinstance(unscheduled, list)
    _assert_coverage(results, unscheduled, courses)
    _assert_hard_constraints(results, courses, classrooms)


def test_empty_courses_returns_empty():
    """空课程列表：返回空 results 和空 unscheduled，不崩溃。"""
    classrooms = [make_classroom(classroom_id=1)]
    results, unscheduled = run_schedule([], classrooms, [])

    assert results == []
    assert unscheduled == []


def test_empty_classrooms_all_unscheduled():
    """无教室：所有课进 unscheduled，不崩溃。"""
    courses = [
        make_course(course_id="C001"),
        make_course(course_id="C002", teacher_ids=["T002"]),
    ]
    results, unscheduled = run_schedule(courses, [], [])

    assert results == []
    assert set(unscheduled) == {"C001", "C002"}


# ══════════════════════════════════════════════════════════════════
# Part 6：性能基线
# ══════════════════════════════════════════════════════════════════

def test_performance_small_scale():
    """性能基线：20课/10教室，2秒内完成，无硬冲突。"""
    n = 20
    courses = [
        make_course(
            course_id=f"C{i:03d}",
            teacher_ids=[f"T{i:03d}"],
            student_count=20 + (i % 30),
        )
        for i in range(n)
    ]
    classrooms = [make_classroom(classroom_id=i, capacity=80) for i in range(10)]

    t0 = time.monotonic()
    results, unscheduled = run_schedule(courses, classrooms, [])
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"小规模应在 2s 内完成，实际 {elapsed:.2f}s"
    _assert_coverage(results, unscheduled, courses)
    _assert_hard_constraints(results, courses, classrooms)


def test_performance_medium_scale():
    """性能基线：100课/30教室（3种房型均分），10秒内完成，无硬冲突。"""
    room_types = [RoomType.LECTURE, RoomType.LAB_CHEMISTRY, RoomType.COMPUTER_LAB]
    n_courses, n_cls = 100, 30

    courses = [
        make_course(
            course_id=f"C{i:04d}",
            teacher_ids=[f"T{i:04d}"],
            student_count=20 + (i % 40),
            room_requirements=[RoomRequirement(room_types[i % 3], 2)],
        )
        for i in range(n_courses)
    ]
    classrooms = [
        make_classroom(classroom_id=i, capacity=80, room_type=room_types[i % 3])
        for i in range(n_cls)
    ]

    t0 = time.monotonic()
    results, unscheduled = run_schedule(courses, classrooms, [])
    elapsed = time.monotonic() - t0

    assert elapsed < 10.0, f"中等规模应在 10s 内完成，实际 {elapsed:.2f}s"
    _assert_coverage(results, unscheduled, courses)
    _assert_hard_constraints(results, courses, classrooms)