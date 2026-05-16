"""
app/algorithm/engine.py
排课算法引擎入口。
当前为占位实现（随机分配），TODO 替换为真实算法逻辑。

算法输入：
  - courses    : 待排课程列表（含教师、学生人数、周课时数等信息）
  - classrooms : 可用教室列表（含校区、容量、类型、基础可用时段）
  - preferences: 教师偏好列表（字段类比 ScheduleEntry，全可选，带 is_negative 极性）

算法输出：
  - list[ScheduleResult] — 每条记录表示一门课的一个时段被分配到某教室

约束条件（TODO 实现）：
  硬约束（必须满足）：
    1. 同一教师同一时间段不能有两门课
    2. 同一教室同一时间段不能有两门课
    3. 教室容量 >= 课程选课人数
    4. 教室类型满足课程需求（实验课必须在实验室）
    5. 时段必须落在教室的 available_slots 内
    6. 跨校区课程不能排在同一教师相邻时段（可选）
  软约束（尽量满足，计入评分）：
    1. 教师偏好（preferences 中 is_negative=False 的条目，命中加分）
    2. 教师禁忌（preferences 中 is_negative=True 的条目，命中扣分）
    3. 同专业课程尽量不冲突
    4. 单天课程数量均匀分布
"""

import random
from dataclasses import dataclass, field


@dataclass
class CourseInput:
    course_id: str
    teacher_ids: list[str]   # 该课程的授课教师 ID 列表（合上时多人）
    student_count: int
    weekly_hours: int        # 每周课时数
    needs_lab: bool = False


@dataclass
class ClassroomInput:
    classroom_id: int
    campus: str
    capacity: int
    is_lab: bool = False
    # 教室基础可用时段集合：{(day_of_week, slot)}
    available_slots: set[tuple[int, int]] = field(default_factory=set)


@dataclass
class TeacherPreference:
    """
    教师对"某门课 / 某种教室 / 某个时段 / 某段周次"的一条偏好。
    除 teacher_id / semester / is_negative 外字段全可选。
    匹配规则与权重由算法实现自定（is_negative=True 视作软扣分或硬约束由算法组决定）。
    """
    teacher_id: str
    semester: str
    course_id: str | None = None
    campus: str | None = None
    building: str | None = None
    classroom_code: str | None = None
    room_type: str | None = None        # "LECTURE" / "LAB" / "GYM"
    day_of_week: int | None = None      # 1-7
    slot_start: int | None = None       # 1-12
    slot_end: int | None = None         # 1-12
    week_start: int | None = None       # 1-16
    week_end: int | None = None         # 1-16
    week_parity: str | None = None      # "ALL" / "ODD" / "EVEN"
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
    week_parity: str = "ALL"   # "ALL" / "ODD" / "EVEN"


def run_schedule(
    courses: list[CourseInput],
    classrooms: list[ClassroomInput],
    preferences: list[TeacherPreference],
) -> tuple[list[ScheduleResult], list[str]]:
    """
    执行排课算法，返回 (成功分配的课表, 未能分配的 course_id 列表)。

    TODO: 用真实的启发式/遗传/回溯算法替换此 stub 实现。
        - preferences 的匹配规则与软硬约束权重由算法实现自定。
        - is_negative=True 的条目通常作为软扣分；如算法组决定按硬约束处理，
          需在文档中明确并在评分函数中实现。
    当前 stub 行为：随机为每门课选一个满足容量约束的教室和时间段，不检查冲突，
    也不消费 preferences。
    """
    results: list[ScheduleResult] = []
    unscheduled: list[str] = []

    _ = preferences  # 占位：算法接入时消费

    for course in courses:
        eligible_rooms = [
            r for r in classrooms
            if r.capacity >= course.student_count
            and (not course.needs_lab or r.is_lab)
        ]
        if not eligible_rooms:
            unscheduled.append(course.course_id)
            continue

        room = random.choice(eligible_rooms)

        # 简单占位：随机选一个时段
        results.append(ScheduleResult(
            course_id=course.course_id,
            teacher_ids=list(course.teacher_ids),
            classroom_id=room.classroom_id,
            day_of_week=random.randint(1, 5),
            slot_start=random.choice([1, 3, 5, 7, 9]),
            slot_end=2,   # stub: 每次排2节
        ))

    return results, unscheduled
