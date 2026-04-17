"""
app/tasks/celery_app.py
Celery 实例初始化。
Worker 启动命令：celery -A app.tasks.celery_app.celery_app worker --loglevel=info
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "course_arrangement",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.scheduler_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 任务结果保留 24 小时
    result_expires=86400,
    # Worker 并发数（CPU 密集型任务建议等于 CPU 核数）
    worker_concurrency=4,
    # 任务超时 30 分钟（排课算法上限）
    task_soft_time_limit=1800,
    task_time_limit=1900,
)
