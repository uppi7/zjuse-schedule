"""
app/main.py
FastAPI 应用入口：挂载路由、注册中间件、管理生命周期。
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.external_clients import close_info_client
from app.api.v1 import classrooms, schedule


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 启动 ───────────────────────────────────────────────────────────
    print(f"[{settings.APP_NAME}] v{settings.APP_VERSION} starting up...")
    await init_db()
    yield
    # ── 关闭 ───────────────────────────────────────────────────────────
    await close_info_client()
    print(f"[{settings.APP_NAME}] shut down.")


app = FastAPI(
    title="自动排课子系统 API",
    description="大型软件工程教学服务系统 — 第二子系统（自动排课组）",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── 中间件 ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO: 生产环境改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局异常处理 ───────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 2000, "msg": str(exc), "data": None},
    )

# ── 路由注册 ───────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(classrooms.router, prefix=API_PREFIX)
app.include_router(schedule.router, prefix=API_PREFIX)


@app.get("/health", tags=["健康检查"])
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
