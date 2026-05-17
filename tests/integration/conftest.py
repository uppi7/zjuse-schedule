"""
tests/integration/conftest.py
integration 层 fixture：连接 docker-compose.test.yml 暴露的真实 MySQL/Redis/Celery 栈

前置条件：docker compose -f docker-compose.test.yml up -d --wait

本层 fixture 通过 httpx 打 http://localhost:8003 的真实 FastAPI 进程，与 unit 层使用的 ASGITransport 不同——这里走真实网络、真实 MySQL 持久化、真实 Celery 任务

未来扩展（测试自行决定是否需要）：
  - 直连 MySQL（localhost:3308）做断言：可加 aiomysql session fixture
  - 直连 Redis（localhost:6381）查 Celery 任务状态：可加 redis client fixture
"""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient

# integration 栈的入口地址。docker-compose.test.yml 暴露在 8003
INTEGRATION_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:8003")


def _stack_ready() -> bool:
    """检测 docker-compose.test.yml 是否已起来；未起则跳过整个 integration 层。"""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(f"{INTEGRATION_BASE_URL}/health", timeout=2) as r:
            return r.status == 200
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_integration_stack():
    """integration 层栈未起则全部 skip。"""
    if not _stack_ready():
        pytest.skip(
            f"integration 栈未就绪：{INTEGRATION_BASE_URL}/health 不可达。"
            "请先运行 `docker compose -f docker-compose.test.yml up -d --wait`。",
            allow_module_level=True,
        )


@pytest_asyncio.fixture
async def integration_client() -> AsyncClient:
    """ADMIN 角色，打真实栈。每个测试一个 client。"""
    async with AsyncClient(
        base_url=INTEGRATION_BASE_URL,
        headers={
            "X-User-Id": "integration-admin",
            "X-User-Role": "ADMIN",
        },
        timeout=30.0,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def integration_student_client() -> AsyncClient:
    """STUDENT 角色，用于权限断言。"""
    async with AsyncClient(
        base_url=INTEGRATION_BASE_URL,
        headers={
            "X-User-Id": "integration-student",
            "X-User-Role": "STUDENT",
        },
        timeout=30.0,
    ) as ac:
        yield ac
