"""
app/core/database.py
SQLAlchemy 异步引擎与 Session 工厂。
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """FastAPI 依赖：提供数据库 Session，请求结束后自动关闭。"""
    async with AsyncSessionLocal() as session:
        yield session
