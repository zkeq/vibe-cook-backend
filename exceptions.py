# coding: utf-8
"""
统一异常处理模块
定义业务异常类和全局异常处理器
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from logger import app_logger


class BusinessException(Exception):
    """业务异常基类"""

    def __init__(self, code: int, message: str, details: str = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class AuthException(BusinessException):
    """认证异常"""

    def __init__(self, message: str = "认证失败", details: str = None):
        super().__init__(401, message, details)


class PermissionException(BusinessException):
    """权限异常"""

    def __init__(self, message: str = "权限不足", details: str = None):
        super().__init__(403, message, details)


class NotFoundException(BusinessException):
    """资源不存在异常"""

    def __init__(self, message: str = "资源不存在", details: str = None):
        super().__init__(404, message, details)


class ValidationException(BusinessException):
    """数据验证异常"""

    def __init__(self, message: str = "数据验证失败", details: str = None):
        super().__init__(400, message, details)


class ConcurrentException(BusinessException):
    """并发操作异常"""

    def __init__(self, message: str = "操作太频繁,请稍后再试", details: str = None):
        super().__init__(429, message, details)


# 全局异常处理器
async def business_exception_handler(request: Request, exc: BusinessException):
    """业务异常处理器"""
    app_logger.warning(
        f"业务异常: code={exc.code}, message={exc.message}, "
        f"path={request.url.path}, details={exc.details}"
    )
    return JSONResponse(
        status_code=exc.code,
        content={
            "success": False,
            "code": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    app_logger.error(
        f"未捕获的异常: {str(exc)}, path={request.url.path}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": 500,
            "message": "服务器内部错误",
            "details": str(exc) if app_logger.level == 10 else None  # DEBUG模式才返回详情
        }
    )
