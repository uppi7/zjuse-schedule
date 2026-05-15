"""
app/algorithm/engine.py
排课算法引擎入口。
当前为占位实现（随机分配），TODO 替换为真实算法逻辑。

算法输入：
  - courses   : 待排课程列表（含教师、学生人数、周课时数等信息）
  - teachers  : 教师可用时间段
  - classrooms: 可用教室列表（含校区、容量、类型、基础可用时段）

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
    1. 教师偏好时间段
    2. 同专业课程尽量不冲突
    3. 单天课程数量均匀分布
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
class TeacherAvailability:
    teacher_id: str
    # 可用时间：{(day_of_week, slot_start): True}
    available_slots: set[tuple[int, int]]


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
    teachers: list[TeacherAvailability],
) -> tuple[list[ScheduleResult], list[str]]:
    """
    执行排课算法，返回 (成功分配的课表, 未能分配的 course_id 列表)。

    TODO: 用真实的启发式/遗传/回溯算法替换此 stub 实现。
    当前 stub 行为：随机为每门课选一个满足容量约束的教室和时间段，不检查冲突。
    """
    results: list[ScheduleResult] = []
    unscheduled: list[str] = []

    teacher_map = {t.teacher_id: t for t in teachers}

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
