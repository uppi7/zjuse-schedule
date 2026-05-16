"""
app/core/exception_handlers.py
全局异常处理：把异常统一渲染为 ApiResponse({code, msg, data})。

契约：
  - 业务异常 / 校验失败 / FastAPI 内置 HTTPException → HTTP 200 + body.code≠0
  - 未捕获异常 → HTTP 500 + {code: 5000, ...}（真挂了仍要 5xx，便于网关区分）
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.response import ApiResponse, BizCode, BizException


# HTTP 状态码 → 业务码 的兜底映射（用于第三方/FastAPI 自身抛的 HTTPException）
_HTTP_TO_BIZ = {
    status.HTTP_401_UNAUTHORIZED: BizCode.UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN: BizCode.FORBIDDEN,
    status.HTTP_404_NOT_FOUND: BizCode.NOT_FOUND,
}


def _json_200(body: ApiResponse) -> JSONResponse:
    return JSONResponse(status_code=200, content=body.model_dump())


async def _biz_exception_handler(_: Request, exc: BizException) -> JSONResponse:
    return _json_200(ApiResponse.fail(code=exc.code, msg=exc.msg, data=exc.data))


async def _validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return _json_200(
        ApiResponse.fail(
            code=BizCode.VALIDATION_ERROR,
            msg="参数校验失败",
            data=exc.errors(),
        )
    )


async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """兜底 FastAPI 内置 / 第三方库抛出的 HTTPException
    业务代码不应再走这条路径——它们应该抛 BizException
    """
    code = _HTTP_TO_BIZ.get(exc.status_code, BizCode.GENERAL_ERROR)
    return _json_200(ApiResponse.fail(code=code, msg=str(exc.detail)))


async def _unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ApiResponse.fail(
            code=BizCode.INTERNAL_ERROR, msg=str(exc)
        ).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BizException, _biz_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
