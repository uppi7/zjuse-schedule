"""
app/core/config.py
全局环境变量与配置管理，基于 Pydantic BaseSettings。
所有配置项均可通过同名环境变量或 .env 文件覆盖。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────
    APP_NAME: str = "automatic-course-arrangement"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── MySQL ─────────────────────────────────────────────────────────────
    MYSQL_HOST: str = "mysql"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "rootpassword"
    MYSQL_DB: str = "course_arrange"

    @property
    def DATABASE_URL(self) -> str:
        # aiomysql 异步驱动
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # TODO: [外部规范协商] 与大组确认排课组占用的 Redis DB 编号，防止与其他子系统冲突。
    # 当前占用 DB 2（Celery broker）和 DB 3（Celery result backend）。
    CELERY_BROKER_DB: int = 2
    CELERY_RESULT_DB: int = 3

    @property
    def CELERY_BROKER_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_BROKER_DB}"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_RESULT_DB}"

    # ── 上游微服务（基础信息组） ────────────────────────────────────────────
    # TODO: [外部规范协商] 与第一组(基础信息组)确认内网服务名、端口和 URL 路径。
    INFO_SERVICE_BASE_URL: str = "http://info-service:8000"
    INFO_SERVICE_TEACHERS_PATH: str = "/api/v1/teachers"
    INFO_SERVICE_COURSES_PATH: str = "/api/v1/courses"
    INFO_SERVICE_CLASSROOMS_PATH: str = "/api/v1/classrooms"

    # ── 认证 Header 字段名（网关透传） ────────────────────────────────────
    # TODO: [外部规范协商] 与第一组及网关负责人确认 Header 字段名。
    AUTH_HEADER_USER_ID: str = "X-User-Id"
    AUTH_HEADER_USER_ROLE: str = "X-User-Role"

    # TODO: [外部规范协商] 确认"教务管理员"角色的 Role Code。
    ROLE_ADMIN: str = "ADMIN"
    ROLE_TEACHER: str = "TEACHER"
    ROLE_STUDENT: str = "STUDENT"


@lru_cache
def get_settings() -> Settings:
    """返回单例配置对象（进程生命周期内只初始化一次）。"""
    return Settings()


settings = get_settings()
