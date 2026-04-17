"""
app/schemas/response.py
全局统一 API 响应格式。所有接口必须使用此包装类返回数据。

格式：{"code": int, "msg": str, "data": Any}

TODO: [外部规范协商] 向大组申请并确认本子系统（排课组）的业务错误码号段。
当前占位方案：
  - 0        : 成功
  - 2000     : 通用业务错误（排课组）
  - 2001     : 教室不存在
  - 2002     : 排课任务未找到
  - 2003     : 无权限执行此操作
  - 2004     : 排课任务正在进行中，请勿重复触发
  - 2005     : 上游服务数据拉取失败
  - 2099     : 排课算法无解（约束冲突）
  正式使用前需与大组确认，避免与其他子系统冲突。
"""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    msg: str = "success"
    data: T | None = None

    @classmethod
    def ok(cls, data: Any = None, msg: str = "success") -> "ApiResponse":
        return cls(code=0, msg=msg, data=data)

    @classmethod
    def fail(cls, code: int, msg: str, data: Any = None) -> "ApiResponse":
        return cls(code=code, msg=msg, data=data)


# ── 业务错误码常量 ────────────────────────────────────────────────────────

class BizCode:
    SUCCESS = 0

    # 排课组错误码段（2000–2099）—— 待大组确认
    GENERAL_ERROR = 2000
    CLASSROOM_NOT_FOUND = 2001
    TASK_NOT_FOUND = 2002
    PERMISSION_DENIED = 2003
    TASK_ALREADY_RUNNING = 2004
    UPSTREAM_FETCH_FAILED = 2005
    ALGORITHM_NO_SOLUTION = 2099
