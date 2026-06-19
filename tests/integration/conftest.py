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
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import redis.asyncio as redis
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# integration 栈的入口地址。docker-compose.test.yml 暴露在 8003
INTEGRATION_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:8003")


def _mysql_url() -> str:
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3308"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "testpassword")
    db = os.getenv("MYSQL_DB", "schedule_test")
    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{db}"


def _redis_url(db_index: int) -> str:
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6381"))
    password = os.getenv("REDIS_PASSWORD", "")
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{host}:{port}/{db_index}"


def _stack_ready() -> bool:
    """检测 docker-compose.test.yml 是否已起来；未起则跳过整个 integration 层。"""
    import urllib.error
    import urllib.request

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
async def integration_client() -> AsyncIterator[AsyncClient]:
    """SYS_ADMIN 角色，打真实栈。每个测试一个 client。"""
    async with AsyncClient(
        base_url=INTEGRATION_BASE_URL,
        headers={
            "X-User-Id": "integration-admin",
            "X-User-Role": "SYS_ADMIN",
        },
        timeout=60.0,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def integration_student_client() -> AsyncIterator[AsyncClient]:
    """STUDENT 角色，用于权限断言。"""
    async with AsyncClient(
        base_url=INTEGRATION_BASE_URL,
        headers={
            "X-User-Id": "integration-student",
            "X-User-Role": "STUDENT",
        },
        timeout=60.0,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def integration_mysql_engine() -> AsyncIterator[AsyncEngine]:
    """直连测试栈 MySQL，用于黑盒断言和清理。"""
    engine = create_async_engine(_mysql_url(), pool_pre_ping=False)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def integration_redis_client() -> AsyncIterator[redis.Redis]:
    """直连测试栈 Redis（Celery result backend）。"""
    client = redis.Redis.from_url(_redis_url(3), decode_responses=False)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture(autouse=True)
async def _ensure_integration_schema(integration_mysql_engine: AsyncEngine):
    """让本地/CI 的测试栈 schema 至少包含当前代码依赖的字段。"""
    async with integration_mysql_engine.begin() as conn:
        exists_result = await conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'schedule_tasks'
                  AND COLUMN_NAME = 'result_meta'
                """
            )
        )
        if int(exists_result.scalar_one()) == 0:
            await conn.execute(text("ALTER TABLE schedule_tasks ADD COLUMN result_meta JSON NULL"))

        for column_name, ddl in {
            "offering_id": "ALTER TABLE schedule_entries ADD COLUMN offering_id VARCHAR(32) NULL",
            "course_code": "ALTER TABLE schedule_entries ADD COLUMN course_code VARCHAR(64) NULL",
            "course_name": "ALTER TABLE schedule_entries ADD COLUMN course_name VARCHAR(128) NULL",
        }.items():
            exists_result = await conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'schedule_entries'
                      AND COLUMN_NAME = :column_name
                    """
                ),
                {"column_name": column_name},
            )
            if int(exists_result.scalar_one()) == 0:
                await conn.execute(text(ddl))
