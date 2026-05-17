"""
tests/integration/test_celery_tasks.py
Celery 任务集成测试：通过真实 worker 验证任务派发/重试/状态汇报。

Owner: tester
覆盖目标：scheduler.run_auto_schedule 任务的全生命周期。
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="TODO(tester): 任务派发用例")
async def test_run_auto_schedule_dispatched_to_worker(integration_client: AsyncClient):
    """
    TODO(tester):
    需求：触发排课后，Redis 中应当出现 celery-task-meta-<task_id> key。

    预期成果：
      - POST /auto-schedule 返回的 task_id
      - 直连 Redis（localhost:6381）能查到对应 meta key
      - meta 内 status 在合理状态机里（PENDING / PROGRESS / SUCCESS / FAILURE）
    """
    raise NotImplementedError


@pytest.mark.skip(reason="TODO(tester): 任务进度上报")
async def test_progress_updates_visible_during_execution(integration_client: AsyncClient):
    """
    TODO(tester):
    需求：scheduler_tasks.run_auto_schedule 在执行过程中会调 update_state
    上报 progress=10/30/70/90。任务运行中至少能轮询到一次 PROGRESS 状态。

    预期成果：以 0.5s 间隔轮询 schedule-status，能至少捕获一次 status=PROGRESS
    且 progress 在 (0, 100) 范围。
    """
    raise NotImplementedError


@pytest.mark.skip(reason="TODO(tester): 失败重试")
async def test_task_failure_triggers_retry(integration_client: AsyncClient):
    """
    TODO(tester):
    需求：scheduler_tasks 配置了 max_retries=2。当 _fetch_upstream_data 抛异常
    时（上游不可达），任务应当重试 2 次后转 FAILURE。

    实现提示：可通过 monkeypatch _fetch_upstream_data 或断网上游服务模拟失败。
    """
    raise NotImplementedError
