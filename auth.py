# coding: utf-8
"""
认证模块
包含 JWT 认证、密码校验、短信验证码(基于进程内内存存储)

说明: 短信验证码这里只做了存储 + 校验的通用流程,
真实发送短信需要你接入自己的短信服务商(阿里云/腾讯云/极光等),
在 send_sms_code 中替换 TODO 部分即可。
"""

import jwt
import random
import yaml
import os
import bcrypt
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db import r
from logger import auth_logger

# 读取配置
config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    CONFIG = yaml.safe_load(file)

JWT_SECRET = CONFIG['JWT']['secret_key']
JWT_ALGORITHM = CONFIG['JWT']['algorithm']
JWT_EXPIRE_MINUTES = CONFIG['JWT']['expire_minutes']

# 定义HTTPBearer安全方案
security = HTTPBearer()


# ==================== 密码相关 ====================

def hash_password(password: str) -> str:
    """使用 bcrypt 加密密码"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt hash 是否匹配"""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception as e:
        auth_logger.error(f"密码校验异常: {str(e)}")
        return False


# ==================== JWT Token 相关 ====================

def create_token(user_id: int, phone: str, role: str = 'user') -> str:
    """
    生成JWT token

    Args:
        user_id: 用户ID
        phone: 手机号
        role: 用户角色

    Returns:
        JWT token字符串
    """
    payload = {
        'user_id': user_id,
        'phone': phone,
        'role': role,
        'exp': datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    auth_logger.info(f"生成Token成功: user_id={user_id}, phone={phone}, role={role}")
    return token


def decode_token(token: str) -> dict:
    """
    解码JWT token

    Args:
        token: JWT token字符串

    Returns:
        解码后的payload字典

    Raises:
        HTTPException: token无效或过期
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        auth_logger.warning(f"Token已过期: {token[:20]}...")
        raise HTTPException(status_code=401, detail="Token已过期")
    except jwt.InvalidTokenError as e:
        auth_logger.warning(f"Token无效: {token[:20]}... - {str(e)}")
        raise HTTPException(status_code=401, detail="Token无效")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    从请求中获取当前用户信息(FastAPI依赖注入)

    Args:
        credentials: HTTPBearer自动提取的认证凭据

    Returns:
        用户信息字典

    Raises:
        HTTPException: 未提供token或token无效
    """
    token = credentials.credentials
    payload = decode_token(token)
    return payload


# ==================== 权限检查依赖注入 ====================

async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    要求管理员权限的依赖注入函数

    使用方式:
        @api.get("/admin/xxx")
        async def xxx(user: dict = Depends(require_admin)):
            # user 已经是管理员
    """
    user = await get_current_user(credentials)
    if user['role'] != 'admin':
        auth_logger.warning(f"权限不足: user_id={user['user_id']}, role={user['role']}, required=admin")
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def require_editor(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    要求编辑(editor)权限的依赖注入函数

    使用方式:
        @api.post("/editor/xxx")
        async def xxx(user: dict = Depends(require_editor)):
            # user 已经是编辑或管理员
    """
    user = await get_current_user(credentials)
    if user['role'] not in ['editor', 'admin']:
        auth_logger.warning(f"权限不足: user_id={user['user_id']}, role={user['role']}, required=editor")
        raise HTTPException(status_code=403, detail="需要编辑权限")
    return user


# ==================== 短信验证码 ====================

def send_sms_code(phone: str) -> dict:
    """
    发送短信验证码

    生成 6 位验证码并存入内存存储(有效期 5 分钟)。
    真实发送短信请在下方 TODO 处接入你的短信服务商。

    Args:
        phone: 手机号

    Returns:
        {"success": bool, "message": str, "code": Optional[str]}
    """
    try:
        # 生成6位验证码
        code = str(random.randint(100000, 999999))

        # 存入内存存储,有效期5分钟
        cache_key = f"sms_code:{phone}"
        r.setex(cache_key, 300, code)

        # TODO: 接入短信服务商,真实发送验证码
        #   例如阿里云/腾讯云/极光短信,在这里调用其 API

        auth_logger.info(f"发送短信验证码: phone={phone}, code={code}")

        # 仅调试模式直接返回验证码,方便本地测试
        return {
            "success": True,
            "message": "验证码发送成功",
            "code": code if CONFIG['SERVER']['debug'] else None
        }

    except Exception as e:
        auth_logger.error(f"发送短信验证码失败: phone={phone}, error={str(e)}")
        return {
            "success": False,
            "message": f"发送失败: {str(e)}"
        }


def verify_sms_code(phone: str, code: str) -> bool:
    """
    验证短信验证码

    Args:
        phone: 手机号
        code: 验证码

    Returns:
        验证是否成功
    """
    try:
        cache_key = f"sms_code:{phone}"
        stored_code = r.get(cache_key)

        if not stored_code:
            auth_logger.warning(f"验证码不存在或已过期: phone={phone}")
            return False

        if stored_code != code:
            auth_logger.warning(f"验证码错误: phone={phone}")
            return False

        # 验证成功后删除验证码
        r.delete(cache_key)
        auth_logger.info(f"验证码验证成功: phone={phone}")
        return True

    except Exception as e:
        auth_logger.error(f"验证码验证失败: phone={phone}, error={str(e)}")
        return False
