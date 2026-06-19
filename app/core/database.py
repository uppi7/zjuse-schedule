"""
app/core/database.py
SQLAlchemy 异步引擎与 Session 工厂。
"""

import asyncio

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=False,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """应用启动时自动建表（不存在则创建，已存在则跳过）。"""
    import app.models  # noqa: F401 — 确保所有 Model 已注册到 Base.metadata

    last_exc: Exception | None = None
    for attempt in range(1, 31):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return
        except OperationalError as exc:
            last_exc = exc
            if attempt == 30:
                break
            await asyncio.sleep(2)

    if last_exc:
        raise last_exc


async def get_db() -> AsyncSession:
    """FastAPI 依赖：提供数据库 Session，请求结束后自动关闭。"""
    async with AsyncSessionLocal() as session:
        yield session
