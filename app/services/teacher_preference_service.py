"""
app/services/teacher_preference_service.py
教师排课偏好业务逻辑。

所有写操作必须做 teacher_id 归属校验：
  - 读出目标行后比较 row.teacher_id 与传入 teacher_id；
  - 不等则抛 `raise BizException(BizCode.PERMISSION_DENIED, "...")`

list_for_algorithm 是给 scheduler_tasks._fetch_upstream_data 调用的，
返回 engine.TeacherPreference dataclass 列表（不返回 ORM 对象），
让算法层不依赖 SQLAlchemy。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.algorithm import engine
from app.models.teacher_preference import TeacherPreference
from app.schemas.teacher_preference import (
    TeacherPreferenceCreate, TeacherPreferenceUpdate,
)


async def create_preference(
    db: AsyncSession,
    teacher_id: str,
    data: TeacherPreferenceCreate,
) -> TeacherPreference:
    """
    新增一条教师偏好。

    输入：
      db          ── 异步 DB session
      teacher_id  ── 从 X-User-Id 注入的归属人
      data        ── TeacherPreferenceCreate（不含 teacher_id）

    输出：持久化后的 TeacherPreference 行（含 id / created_at / updated_at）

    实现要点：
      obj = TeacherPreference(teacher_id=teacher_id, **data.model_dump())
      db.add(obj); await db.commit(); await db.refresh(obj); return obj
    """
    raise NotImplementedError("TODO: 实现 create_preference")


async def get_preference(
    db: AsyncSession,
    pref_id: int,
    teacher_id: str,
) -> TeacherPreference:
    """
    按主键取一条偏好；校验归属。

    输入：
      pref_id     ── teacher_preferences.id
      teacher_id  ── 当前调用者的 user_id；不等于行的 teacher_id 时 403

    输出：TeacherPreference 行

    错误：
      404 BizCode.GENERAL_ERROR  — 行不存在
      403 BizCode.PERMISSION_DENIED — 行存在但不属于该 teacher
    """
    raise NotImplementedError("TODO: 实现 get_preference")


async def list_preferences(
    db: AsyncSession,
    teacher_id: str,
    semester: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[TeacherPreference]:
    """
    列出某教师的偏好；可选按 semester 过滤。

    输入：
      teacher_id  ── 仅返回 row.teacher_id==teacher_id 的行
      semester    ── 可选过滤
      skip/limit  ── 分页

    输出：list[TeacherPreference]，按 id 升序或 created_at 降序皆可

    实现要点：
      stmt = select(TP).where(TP.teacher_id == teacher_id)
      if semester: stmt = stmt.where(TP.semester == semester)
      stmt = stmt.offset(skip).limit(limit)
    """
    raise NotImplementedError("TODO: 实现 list_preferences")


async def update_preference(
    db: AsyncSession,
    pref_id: int,
    teacher_id: str,
    data: TeacherPreferenceUpdate,
) -> TeacherPreference:
    """
    PATCH 半字段更新；校验归属。

    输入：
      data ── 仅更新 model_dump(exclude_unset=True) 中出现的字段

    实现要点：
      obj = await get_preference(db, pref_id, teacher_id)  # 内含 404/403
      for field, value in data.model_dump(exclude_unset=True).items():
          setattr(obj, field, value)
      await db.commit(); await db.refresh(obj); return obj

      注：使用 exclude_unset（不是 exclude_none），允许将字段显式置为 None。
    """
    raise NotImplementedError("TODO: 实现 update_preference")


async def delete_preference(
    db: AsyncSession,
    pref_id: int,
    teacher_id: str,
) -> None:
    """
    删除一条偏好；校验归属。

    实现要点：
      obj = await get_preference(db, pref_id, teacher_id)
      await db.delete(obj); await db.commit()
    """
    raise NotImplementedError("TODO: 实现 delete_preference")


async def list_for_algorithm(
    db: AsyncSession,
    semester: str,
) -> list[engine.TeacherPreference]:
    """
    供 scheduler_tasks._fetch_upstream_data 调用：按学期拉取所有教师偏好，
    映射为算法 dataclass 列表。

    输入：
      semester ── 必填；仅返回该学期的偏好

    输出：list[engine.TeacherPreference]（dataclass，不是 ORM 对象）

    实现要点：
      rows = (await db.execute(
          select(TeacherPreference).where(TeacherPreference.semester == semester)
      )).scalars().all()

      return [
          engine.TeacherPreference(
              teacher_id=r.teacher_id,
              semester=r.semester,
              course_id=r.course_id,
              campus=r.campus,
              building=r.building,
              classroom_code=r.classroom_code,
              room_type=r.room_type.value if r.room_type else None,
              day_of_week=int(r.day_of_week) if r.day_of_week else None,
              slot_start=r.slot_start,
              slot_end=r.slot_end,
              week_start=r.week_start,
              week_end=r.week_end,
              week_parity=r.week_parity.value if r.week_parity else None,
              is_negative=r.is_negative,
          )
          for r in rows
      ]

    规模注意：当前不分页、不缓存；数据量大时再优化（如流式或分批）。
    """
    raise NotImplementedError("TODO: 实现 list_for_algorithm")
