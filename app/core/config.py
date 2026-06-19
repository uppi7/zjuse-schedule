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
        extra="ignore",
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
            return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # 排课组占用 Redis DB 2（Celery broker）和 DB 3（Celery result backend）
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

    # ── 上游微服务（经 Gateway 调用 Auth / Info）────────────────────────────
    GATEWAY_BASE_URL: str = "http://gateway:8000"
    SCHEDULE_SERVICE_CLIENT_ID: str = "schedule_service"
    SCHEDULE_SERVICE_CLIENT_SECRET: str = "change-me-schedule-service-secret"
    AUTH_SYS_LOGIN_PATH: str = "/auth/sys/login"
    INFO_OFFERINGS_PATH: str = "/api/v1/info/offerings/"
    INFO_COURSES_PATH: str = "/api/v1/info/courses/"
    INFO_OFFERING_TEACHERS_PATH_TEMPLATE: str = (
        "/api/v1/info/offerings/{offering_id}/teachers"
    )
    ALLOW_UPSTREAM_STUB_FALLBACK: bool = False

    # ── 认证 Header 字段名（网关透传）────────────────────────────────────────
    # 网关在转发请求时将已认证的用户信息写入以下 Header
    AUTH_HEADER_USER_ID: str = "X-User-Id"
    AUTH_HEADER_USER_ROLE: str = "X-User-Role"

    # 角色枚举值
    ADMIN_ROLES: set[str] = {"SYS_ADMIN", "ACADEMIC_ADMIN"}
    ROLE_TEACHER: str = "TEACHER"
    ROLE_STUDENT: str = "STUDENT"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
