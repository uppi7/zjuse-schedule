"""
tests/e2e/conftest.py
E2E 层 fixture：API 级端到端，httpx 打 docker-compose.test.yml 暴露的端口。

前置：docker compose -f docker-compose.test.yml up -d --wait
"""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient

E2E_BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8003")


def _stack_ready() -> bool:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"{E2E_BASE_URL}/health", timeout=2) as r:
            return r.status == 200
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_e2e_stack():
    if not _stack_ready():
        pytest.skip(
            f"E2E 栈未就绪：{E2E_BASE_URL}/health 不可达。"
            "请先运行 `docker compose -f docker-compose.test.yml up -d --wait`。",
            allow_module_level=True,
        )


@pytest_asyncio.fixture
async def admin_client() -> AsyncClient:
    """SYS_ADMIN 角色 client。"""
    async with AsyncClient(
        base_url=E2E_BASE_URL,
        headers={"X-User-Id": "e2e-admin", "X-User-Role": "SYS_ADMIN"},
        timeout=30.0,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def student_client() -> AsyncClient:
    """STUDENT 角色 client。"""
    async with AsyncClient(
        base_url=E2E_BASE_URL,
        headers={"X-User-Id": "e2e-student", "X-User-Role": "STUDENT"},
        timeout=30.0,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def teacher_client() -> AsyncClient:
    """TEACHER 角色 client，用于 e2e 教师流程测试。"""
    async with AsyncClient(
        base_url=E2E_BASE_URL,
        headers={"X-User-Id": "STUB-T001", "X-User-Role": "TEACHER"},
        timeout=60.0,
    ) as ac:
        yield ac
