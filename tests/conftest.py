"""
tests/conftest.py
pytest 全局 fixture 配置。
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.database import Base, get_db


# ── 测试数据库（SQLite 内存库，无需 MySQL）──────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def create_tables():
    """每次测试会话开始时建表，结束时销毁。"""
    # sqlite 需要 aiosqlite，先安装：pip install aiosqlite
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncSession:
    """提供测试用数据库 Session，每个测试后回滚。"""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """提供测试用 HTTP 客户端，注入测试 DB Session，并附带 ADMIN Header。"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={
            "X-User-Id": "test-admin-001",
            "X-User-Role": "ADMIN",
        },
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def student_client(db_session: AsyncSession) -> AsyncClient:
    """提供学生角色的测试客户端，用于测试权限拦截。"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={
            "X-User-Id": "test-student-001",
            "X-User-Role": "STUDENT",
        },
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
