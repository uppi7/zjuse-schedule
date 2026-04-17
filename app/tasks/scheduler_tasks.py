"""
app/tasks/scheduler_tasks.py
具体的排课异步任务定义。
"""

import time
import asyncio
from celery import shared_task
from celery.utils.log import get_task_logger

from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    name="scheduler.run_auto_schedule",
    max_retries=2,
    default_retry_delay=30,
)
def run_auto_schedule(self, semester: str, triggered_by: str) -> dict:
    """
    排课主任务。由 FastAPI 接口通过 .delay() 调用，运行在 Celery Worker 进程中。

    执行步骤：
      1. 从基础信息组拉取教师、课程、教室数据
      2. 调用排课算法引擎
      3. 将结果写入 MySQL
      4. 通知下游选课组

    当前为 stub 实现，使用 time.sleep 模拟耗时，真实算法替换第2步即可。
    """
    logger.info(f"[run_auto_schedule] START semester={semester}, triggered_by={triggered_by}")

    try:
        # ── Step 1: 拉取上游数据 ─────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"progress": 10, "message": "正在从基础信息组拉取数据..."})
        logger.info("Step 1: fetching upstream data")

        # 在 Celery 同步任务中运行异步代码
        teachers, courses, classrooms = asyncio.run(_fetch_upstream_data())
        logger.info(f"Fetched: teachers={len(teachers)}, courses={len(courses)}, classrooms={len(classrooms)}")

        # ── Step 2: 运行排课算法 ──────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"progress": 30, "message": "正在运行排课算法..."})
        logger.info("Step 2: running schedule algorithm")

        # TODO: 算法组替换此 stub —— 调用 app.algorithm.engine.run_schedule()
        time.sleep(5)   # 模拟算法耗时

        # stub: 生成假结果
        schedule_results = _build_stub_results(courses)
        unscheduled = []

        self.update_state(state="PROGRESS", meta={"progress": 70, "message": "算法完成，正在写入数据库..."})

        # ── Step 3: 写入 MySQL ────────────────────────────────────────────
        logger.info("Step 3: saving results to MySQL")
        time.sleep(1)   # 模拟 DB 写入
        asyncio.run(_save_results(semester, schedule_results))

        # ── Step 4: 通知下游 ──────────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"progress": 90, "message": "正在通知下游系统..."})
        logger.info("Step 4: notifying downstream")
        asyncio.run(_notify_downstream(semester))

        result_summary = {
            "semester": semester,
            "total_courses": len(courses),
            "scheduled": len(schedule_results),
            "unscheduled": unscheduled,
            "unscheduled_count": len(unscheduled),
        }
        logger.info(f"[run_auto_schedule] DONE: {result_summary}")
        return result_summary

    except Exception as exc:
        logger.error(f"[run_auto_schedule] FAILED: {exc}", exc_info=True)
        raise self.retry(exc=exc) if self.request.retries < self.max_retries else exc


# ── 辅助异步函数（在同步 Celery task 中通过 asyncio.run() 调用） ──────────

async def _fetch_upstream_data() -> tuple[list, list, list]:
    """
    从基础信息组和本地 DB 拉取排课所需数据。
    TODO: 替换为真实的 InfoServiceClient 调用和 DB 查询。
    """
    from app.core.external_clients import get_info_client

    client = get_info_client()
    try:
        teachers = await client.get_all_teachers()
        courses = await client.get_all_courses()
    except Exception as e:
        logger.warning(f"Failed to fetch from info service, using stub data: {e}")
        # Fallback stub 数据，便于在上游未就绪时独立测试
        teachers = [{"teacher_id": "T001", "name": "张三"}]
        courses = [{"course_id": "C001", "teacher_id": "T001", "student_count": 50, "weekly_hours": 4}]

    # 教室从本地 DB 读取
    classrooms = [{"classroom_id": 1, "capacity": 120, "is_lab": False}]
    return teachers, courses, classrooms


async def _save_results(semester: str, results: list) -> None:
    """将排课结果写入本地 MySQL。"""
    # TODO: 实现真实的 DB 写入逻辑
    pass


async def _notify_downstream(semester: str) -> None:
    """通知下游选课组。"""
    from app.services.schedule_service import notify_downstream
    await notify_downstream(semester, [])


def _build_stub_results(courses: list) -> list:
    """构造测试用假结果（无真实算法时使用）。"""
    return [{"course_id": c.get("course_id", "UNKNOWN")} for c in courses]
