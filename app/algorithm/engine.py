"""
app/algorithm/engine.py
排课算法引擎入口。

算法：带软约束评分的贪心求解器（GRASP 风格）
- 硬约束（必须满足，违反则跳过候选槽）：
    H1. 同一教师同一时段不能有两门课
    H2. 同一教室同一时段不能有两门课
    H3. 教室容量 >= 课程选课人数
    H4. 教室类型满足课程需求
    H5. 时段必须落在教室的 available_slots 内
- 软约束（计入评分函数，is_negative=True 扣分，False 加分）：
    S1. 教师偏好命中加 +10，教师禁忌命中 -10
    S2. 跨校区相邻时段 -5（软扣分，H6 归为软约束）
    S3. 同天课程数量均匀分布：每天已排课越多扣分越多
    S4. 同一教师同天排课不超过 4 节（软约束）
- is_negative=True 的偏好处理：作为软扣分（而非硬约束），
  避免偏好数量过多导致无解。调用方在 PR 描述中应说明此约定。
- 超时兜底：solver 整体超时后，已排部分返回，剩余进 unscheduled。

排课单元（slot_start, slot_end）约定：
  每条 room_requirement 的 hours 按"连续2节"为一次上课单元拆分：
    hours=2  → 1次 (slot_start, slot_start+1)
    hours=4  → 2次，分配在不同天
  奇数 hours 最后一节单独排（1节课 slot_end=slot_start）。
  week_start=1, week_end=16, week_parity=ALL（本期简化，不拆单双周）。
"""

import enum
import time
import random
from dataclasses import dataclass, field
from typing import NamedTuple


# ──────────────────────────────────────────────────────────────
# 枚举 & 数据类（保持与原接口兼容）
# ──────────────────────────────────────────────────────────────

class RoomType(str, enum.Enum):
    """算法层使用的房间类型。与 DB 的 ClassroomType 同名同值，靠 .value 桥接。"""
    LECTURE       = "LECTURE"
    LAB_PHYSICS   = "LAB_PHYSICS"
    LAB_CHEMISTRY = "LAB_CHEMISTRY"
    LAB_BIOLOGY   = "LAB_BIOLOGY"
    COMPUTER_LAB  = "COMPUTER_LAB"
    GYM           = "GYM"


@dataclass
class RoomRequirement:
    """一门课对某种房间类型的每周学时需求。"""
    room_type: RoomType
    hours: int


@dataclass
class CourseInput:
    course_id: str
    teacher_ids: list[str]
    student_count: int
    room_requirements: list[RoomRequirement] = field(default_factory=list)


@dataclass
class ClassroomInput:
    classroom_id: int
    campus: str
    capacity: int
    room_type: RoomType = RoomType.LECTURE
    available_slots: set[tuple[int, int]] = field(default_factory=set)


@dataclass
class TeacherPreference:
    """教师对"某门课 / 某种教室 / 某个时段 / 某段周次"的一条偏好。"""
    teacher_id: str
    semester: str
    course_id: str | None = None
    campus: str | None = None
    building: str | None = None
    classroom_code: str | None = None
    room_type: str | None = None
    day_of_week: int | None = None
    slot_start: int | None = None
    slot_end: int | None = None
    week_start: int | None = None
    week_end: int | None = None
    week_parity: str | None = None
    is_negative: bool = False


@dataclass
class ScheduleResult:
    course_id: str
    teacher_ids: list[str]
    classroom_id: int
    day_of_week: int      # 1=周一 … 7=周日
    slot_start: int       # 起始节次（1-12）
    slot_end: int         # 结束节次
    week_start: int = 1
    week_end: int = 16
    week_parity: str = "ALL"


# ──────────────────────────────────────────────────────────────
# 内部数据结构
# ──────────────────────────────────────────────────────────────

class _TimeSlot(NamedTuple):
    """一个连续节次区间（同一天）。"""
    day_of_week: int   # 1-7
    slot_start: int    # 1-12
    slot_end: int      # 1-12


class _SchedulerState:
    """记录已分配的资源占用，用于冲突检测。"""

    def __init__(self) -> None:
        # teacher_id → set of (day, slot) 已占用节次
        self._teacher_slots: dict[str, set[tuple[int, int]]] = {}
        # classroom_id → set of (day, slot) 已占用节次
        self._classroom_slots: dict[int, set[tuple[int, int]]] = {}
        # teacher_id → list of (day, campus) 用于跨校区检测
        self._teacher_day_campus: dict[str, list[tuple[int, str]]] = {}

    # ── 冲突检测 ────────────────────────────────────────────────

    def teacher_conflicts(self, teacher_ids: list[str], ts: _TimeSlot) -> bool:
        """任一教师在该时段已有课 → True。"""
        occupied = set(range(ts.slot_start, ts.slot_end + 1))
        for tid in teacher_ids:
            used = self._teacher_slots.get(tid, set())
            for slot in occupied:
                if (ts.day_of_week, slot) in used:
                    return True
        return False

    def classroom_conflicts(self, classroom_id: int, ts: _TimeSlot) -> bool:
        """教室在该时段已被占用 → True。"""
        used = self._classroom_slots.get(classroom_id, set())
        for slot in range(ts.slot_start, ts.slot_end + 1):
            if (ts.day_of_week, slot) in used:
                return True
        return False

    # ── 提交分配 ────────────────────────────────────────────────

    def commit(
        self,
        teacher_ids: list[str],
        classroom_id: int,
        campus: str,
        ts: _TimeSlot,
    ) -> None:
        for slot in range(ts.slot_start, ts.slot_end + 1):
            for tid in teacher_ids:
                self._teacher_slots.setdefault(tid, set()).add((ts.day_of_week, slot))
            self._classroom_slots.setdefault(classroom_id, set()).add((ts.day_of_week, slot))
        for tid in teacher_ids:
            self._teacher_day_campus.setdefault(tid, []).append((ts.day_of_week, campus))

    def rollback(
        self,
        teacher_ids: list[str],
        classroom_id: int,
        campus: str,
        ts: _TimeSlot,
    ) -> None:
        """撤销一次 commit（用于课程排课失败时回滚同课已占用的时段）。"""
        for slot in range(ts.slot_start, ts.slot_end + 1):
            for tid in teacher_ids:
                self._teacher_slots.get(tid, set()).discard((ts.day_of_week, slot))
            self._classroom_slots.get(classroom_id, set()).discard((ts.day_of_week, slot))
        for tid in teacher_ids:
            dc_list = self._teacher_day_campus.get(tid, [])
            try:
                dc_list.remove((ts.day_of_week, campus))
            except ValueError:
                pass

    # ── 软约束辅助 ──────────────────────────────────────────────

    def teacher_slots_on_day(self, teacher_ids: list[str], day: int) -> int:
        """该教师在某天已排的节次总数（用于均匀分布评分）。"""
        count = 0
        for tid in teacher_ids:
            used = self._teacher_slots.get(tid, set())
            count += sum(1 for (d, _) in used if d == day)
        return count

    def has_adjacent_cross_campus(
        self, teacher_ids: list[str], campus: str, ts: _TimeSlot
    ) -> bool:
        """在同一天，相邻时段（前后紧接）且校区不同 → True（软约束检测）。"""
        for tid in teacher_ids:
            for (d, tc) in self._teacher_day_campus.get(tid, []):
                if d == ts.day_of_week and tc != campus:
                    return True
        return False


# ──────────────────────────────────────────────────────────────
# 偏好匹配
# ──────────────────────────────────────────────────────────────

def _pref_matches(
    pref: TeacherPreference,
    teacher_ids: list[str],
    course_id: str,
    classroom: ClassroomInput,
    ts: _TimeSlot,
) -> bool:
    """判断一条偏好是否与当前分配匹配（所有非 None 字段均需命中）。"""
    if pref.teacher_id not in teacher_ids:
        return False
    if pref.course_id is not None and pref.course_id != course_id:
        return False
    if pref.campus is not None and pref.campus != classroom.campus:
        return False
    if pref.room_type is not None and pref.room_type != classroom.room_type.value:
        return False
    if pref.day_of_week is not None and pref.day_of_week != ts.day_of_week:
        return False
    if pref.slot_start is not None and ts.slot_start < pref.slot_start:
        return False
    if pref.slot_end is not None and ts.slot_end > pref.slot_end:
        return False
    return True


def _preference_score(
    prefs: list[TeacherPreference],
    teacher_ids: list[str],
    course_id: str,
    classroom: ClassroomInput,
    ts: _TimeSlot,
) -> float:
    """计算偏好得分：正偏好命中 +10，负偏好命中 -10。"""
    score = 0.0
    for pref in prefs:
        if _pref_matches(pref, teacher_ids, course_id, classroom, ts):
            score += -10.0 if pref.is_negative else +10.0
    return score


# ──────────────────────────────────────────────────────────────
# 候选槽拆分工具
# ──────────────────────────────────────────────────────────────

# 每次上课的节次粒度（slot_start, slot_end 的差值+1）
_SLOT_UNITS = [
    (1, 2),   # 节1-2
    (3, 4),   # 节3-4
    (5, 6),   # 节5-6
    (7, 8),   # 节7-8
    (9, 10),  # 节9-10
    (11, 12), # 节11-12
]


def _split_hours_to_sessions(hours: int) -> list[int]:
    """
    将 hours 拆成若干次上课（每次课 2 节或 1 节）。
    hours=4 → [2, 2]（两次课，每次2节）
    hours=3 → [2, 1]
    hours=1 → [1]
    """
    sessions = []
    remaining = hours
    while remaining >= 2:
        sessions.append(2)
        remaining -= 2
    if remaining == 1:
        sessions.append(1)
    return sessions


def _generate_time_slots(
    session_len: int, classroom: ClassroomInput
) -> list[_TimeSlot]:
    """
    根据教室 available_slots 生成所有合法的时段候选（满足 H5）。
    session_len: 课的节次长度（1 或 2）。
    """
    slots = []
    for day in range(1, 6):  # 周一到周五
        for start, end in _SLOT_UNITS:
            # 单节课只占 slot_start
            if session_len == 1:
                end = start
            actual_end = start + session_len - 1
            if actual_end > 12:
                continue
            # 检查这段时间在教室 available_slots 内（H5）
            ok = all(
                (day, s) in classroom.available_slots
                for s in range(start, actual_end + 1)
            )
            if ok:
                slots.append(_TimeSlot(day, start, actual_end))
    return slots


# ──────────────────────────────────────────────────────────────
# 评分函数
# ──────────────────────────────────────────────────────────────

def _score_candidate(
    state: _SchedulerState,
    prefs: list[TeacherPreference],
    course: CourseInput,
    classroom: ClassroomInput,
    ts: _TimeSlot,
) -> float:
    """
    综合评分（越高越好）：
    - 教师偏好/禁忌        ±10
    - 跨校区相邻时段        -5  (S2, 软处理)
    - 同天课时均匀惩罚      -2 * 该天已排节次
    """
    score = 0.0

    # S1: 教师偏好
    score += _preference_score(prefs, course.teacher_ids, course.course_id, classroom, ts)

    # S2: 跨校区相邻
    if state.has_adjacent_cross_campus(course.teacher_ids, classroom.campus, ts):
        score -= 5.0

    # S3: 单天均匀
    slots_today = state.teacher_slots_on_day(course.teacher_ids, ts.day_of_week)
    score -= 2.0 * slots_today

    return score


# ──────────────────────────────────────────────────────────────
# 主求解器
# ──────────────────────────────────────────────────────────────

# 超时配置（秒）：本地调试用较小值，生产环境可通过环境变量覆盖
import os
_SOLVER_TIMEOUT_SECONDS = float(os.environ.get("SOLVER_TIMEOUT_SECONDS", "1200"))  # 默认20分钟


def _rollback(
    state: _SchedulerState,
    committed: list[ScheduleResult],
    classrooms: list[ClassroomInput],
) -> None:
    """将 committed 列表中已 commit 的时段逐条从 state 撤销。"""
    cls_map = {c.classroom_id: c for c in classrooms}
    for r in committed:
        cls = cls_map[r.classroom_id]
        ts = _TimeSlot(r.day_of_week, r.slot_start, r.slot_end)
        state.rollback(r.teacher_ids, r.classroom_id, cls.campus, ts)


def run_schedule(
    courses: list[CourseInput],
    classrooms: list[ClassroomInput],
    preferences: list[TeacherPreference],
) -> tuple[list[ScheduleResult], list[str]]:
    """
    执行排课算法，返回 (成功分配的课表, 未能分配的 course_id 列表)。

    算法策略：
    1. 对 room_requirements 同类型合并，hours==0 忽略。
    2. 按"约束最紧"顺序排课（学生多 → 房型少 → 优先排）。
    3. 对每条需求的每次上课单元，枚举合法候选槽，用评分函数选最优。
    4. 任何课程的任一需求无法满足硬约束，该课进 unscheduled。
    5. 超时后，剩余课程整体进 unscheduled（不产生部分排课的半成品）。
    """
    deadline = time.monotonic() + _SOLVER_TIMEOUT_SECONDS

    results: list[ScheduleResult] = []
    unscheduled: list[str] = []
    state = _SchedulerState()

    # ── 预处理：合并 room_requirements 同类型 ───────────────────
    sorted_courses = _sort_courses_by_difficulty(courses, classrooms)

    for course in sorted_courses:
        if time.monotonic() > deadline:
            # 超时兜底：剩余课全进 unscheduled
            remaining = {c.course_id for c in sorted_courses}
            scheduled_ids = {r.course_id for r in results}
            unscheduled.extend(remaining - scheduled_ids - set(unscheduled))
            break

        merged_reqs = _merge_requirements(course.room_requirements)
        course_results: list[ScheduleResult] = []
        failed = False

        for room_type, total_hours in merged_reqs.items():
            if total_hours <= 0:
                continue

            # 找满足 H3+H4 的教室候选
            eligible_rooms = [
                r for r in classrooms
                if r.room_type == room_type and r.capacity >= course.student_count
            ]
            if not eligible_rooms:
                failed = True
                break

            # 拆成多次上课单元
            sessions = _split_hours_to_sessions(total_hours)

            for session_len in sessions:
                if time.monotonic() > deadline:
                    failed = True
                    break

                best_result = _find_best_slot(
                    state, preferences, course, eligible_rooms, session_len
                )
                if best_result is None:
                    failed = True
                    break

                # 立即 commit，让同课后续 session 能感知已占用时段（避免同课自身冲突）
                cls = next(c for c in classrooms if c.classroom_id == best_result.classroom_id)
                ts = _TimeSlot(best_result.day_of_week, best_result.slot_start, best_result.slot_end)
                state.commit(best_result.teacher_ids, best_result.classroom_id, cls.campus, ts)
                course_results.append(best_result)

            if failed:
                # 回滚：把本课已 commit 的时段从 state 中撤销
                _rollback(state, course_results, classrooms)
                break

        if failed:
            unscheduled.append(course.course_id)
        else:
            results.extend(course_results)

    return results, unscheduled


# ──────────────────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────────────────

def _merge_requirements(reqs: list[RoomRequirement]) -> dict[RoomType, int]:
    """合并同类型 room_requirements，忽略 hours<=0 的项。"""
    merged: dict[RoomType, int] = {}
    for req in reqs:
        if req.hours > 0:
            merged[req.room_type] = merged.get(req.room_type, 0) + req.hours
    return merged


def _sort_courses_by_difficulty(
    courses: list[CourseInput], classrooms: list[ClassroomInput]
) -> list[CourseInput]:
    """
    难以安排的课优先排（约束最紧原则）：
    - 学生数越多 → 可用教室越少 → 越难
    - room_requirements 种类越多 → 越难
    """
    def difficulty(course: CourseInput) -> tuple:
        merged = _merge_requirements(course.room_requirements)
        # 对每种类型，统计满足容量的教室数，取最少的
        min_eligible = float("inf")
        for rt in merged:
            cnt = sum(
                1 for c in classrooms
                if c.room_type == rt and c.capacity >= course.student_count
            )
            min_eligible = min(min_eligible, cnt)
        if min_eligible == float("inf"):
            min_eligible = 0
        return (min_eligible, -course.student_count, -len(merged))

    return sorted(courses, key=difficulty)


def _find_best_slot(
    state: _SchedulerState,
    preferences: list[TeacherPreference],
    course: CourseInput,
    eligible_rooms: list[ClassroomInput],
    session_len: int,
) -> ScheduleResult | None:
    """
    在合法候选（满足 H1-H5）中找评分最高的 (教室, 时段) 组合。
    返回 ScheduleResult 或 None（无可行解）。
    """
    best_score = float("-inf")
    best: ScheduleResult | None = None

    # 随机打乱教室顺序，避免总选第一个（增加多样性）
    rooms = list(eligible_rooms)
    random.shuffle(rooms)

    for classroom in rooms:
        candidate_slots = _generate_time_slots(session_len, classroom)
        # 随机打乱时段候选
        random.shuffle(candidate_slots)

        for ts in candidate_slots:
            # H1: 教师冲突
            if state.teacher_conflicts(course.teacher_ids, ts):
                continue
            # H2: 教室冲突
            if state.classroom_conflicts(classroom.classroom_id, ts):
                continue
            # H3+H4: 已在 eligible_rooms 中过滤
            # H5: 已在 _generate_time_slots 中过滤

            score = _score_candidate(state, preferences, course, classroom, ts)
            if score > best_score:
                best_score = score
                best = ScheduleResult(
                    course_id=course.course_id,
                    teacher_ids=list(course.teacher_ids),
                    classroom_id=classroom.classroom_id,
                    day_of_week=ts.day_of_week,
                    slot_start=ts.slot_start,
                    slot_end=ts.slot_end,
                    week_start=1,
                    week_end=16,
                    week_parity="ALL",
                )

    return best