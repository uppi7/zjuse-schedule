"""
app/schemas/response.py
全局统一 API 响应格式。所有接口必须使用此包装类返回数据。

格式：{"code": int, "msg": str, "data": Any}

错误响应契约：业务错一律 HTTP 200 + body.code≠0；只有真未捕获异常才返 5xx。
业务代码请抛 BizException，由全局 handler 渲染——不要再 raise HTTPException。

业务错误码（排课组占用 2000–2099 段，通用码也在此段内）：
  0    : 成功

  资源/业务专属码：
  2000 : 通用业务错误
  2001 : 教室不存在
  2002 : 排课任务未找到
  2003 : 无权限执行此操作
  2004 : 排课任务正在进行中，请勿重复触发
  2005 : 上游服务数据拉取失败

  通用技术码：
  2010 : 参数校验失败
  2011 : 未授权
  2012 : 禁止访问
  2013 : 资源不存在
  2098 : 服务内部错误

  算法层：
  2099 : 排课算法无解（约束冲突）
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
    """排课组错误码段：2000–2099（含通用技术码与业务专属码）。"""

    SUCCESS = 0

    # 资源/业务专属码（2000–2009）
    GENERAL_ERROR = 2000
    CLASSROOM_NOT_FOUND = 2001
    TASK_NOT_FOUND = 2002
    PERMISSION_DENIED = 2003
    TASK_ALREADY_RUNNING = 2004
    UPSTREAM_FETCH_FAILED = 2005

    # 通用技术码（2010–2019）
    VALIDATION_ERROR = 2010
    UNAUTHORIZED = 2011
    FORBIDDEN = 2012
    NOT_FOUND = 2013

    # 服务/算法层（2090–2099）
    INTERNAL_ERROR = 2098
    ALGORITHM_NO_SOLUTION = 2099


# ── 业务异常 ───────────────────────────────────────────────────────────────

class BizException(Exception):
    """
    业务异常。由全局 handler 渲染为 HTTP 200 + ApiResponse({code, msg, data})。
    业务代码统一抛此异常，禁止再 raise HTTPException。
    """

    def __init__(self, code: int, msg: str, data: Any = None):
        self.code = code
        self.msg = msg
        self.data = data
        super().__init__(msg)
