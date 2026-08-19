# coding: utf-8
"""
Vibe Cook Backend - 主入口文件
极简架构: Request → router → auth → business → SQL → Response
"""

import uvicorn
import yaml
import os
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer
from starlette.middleware.cors import CORSMiddleware
from router import api
from logger import app_logger, api_logger
from exceptions import (
    BusinessException,
    business_exception_handler,
    general_exception_handler
)

# 读取配置
config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    CONFIG = yaml.safe_load(file)

# 定义安全方案
security = HTTPBearer()

# 创建FastAPI应用
app = FastAPI(
    title="Vibe Cook Backend",
    description="极简 FastAPI 后端模板 (JWT 认证 + 用户管理)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "persistAuthorization": True  # 刷新页面后保持登录状态
    }
)

# 自定义OpenAPI schema以添加安全方案
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # 添加Bearer Token认证方案
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "输入格式: Bearer <token>"
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境需要限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册异常处理器
app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


# ==================== 中间件 ====================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    api_logger.info(f"[{current_time}] {request.method} {request.url}")

    response = await call_next(request)
    return response


@app.middleware("http")
async def error_handler(request: Request, call_next):
    """全局错误处理中间件(已由异常处理器替代,保留用于其他用途)"""
    response = await call_next(request)
    return response


# ==================== 路由挂载 ====================

# 挂载静态文件服务
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# 挂载API路由 (v1版本)
app.include_router(api, prefix="/api/v1", tags=["v1"])


# ==================== 基础路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "Vibe Cook Backend",
        "version": "1.0.0",
        "status": "running",
        "message": "极简架构后端服务"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# ==================== 启动配置 ====================

if __name__ == "__main__":
    host = CONFIG['SERVER']['host']
    port = CONFIG['SERVER']['port']
    debug = CONFIG['SERVER']['debug']

    app_logger.info(f"=" * 60)
    app_logger.info(f"Vibe Cook Backend 启动中...")
    app_logger.info(f"服务地址: http://{host}:{port}")
    app_logger.info(f"API文档: http://{host}:{port}/docs")
    app_logger.info(f"调试模式: {'开启' if debug else '关闭'}")
    app_logger.info(f"=" * 60)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
