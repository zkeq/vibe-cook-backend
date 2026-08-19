# coding: utf-8
"""
用户管理业务逻辑模块

这是所有 business 层函数的范式参考:
- 使用 get_db_connection() 获取连接
- 使用参数化查询 (?) 防止 SQL 注入
- 使用 DictCursor (自动) 返回字典结果
- 记录带上下文的错误日志
- 在 finally 中关闭 cursor 和 connection
- 写操作使用 conn.commit() / conn.rollback()
"""

from typing import Optional
from db import get_db_connection
from logger import business_logger


def get_or_create_user_by_phone(phone: str, nickname: str = None, avatar: str = None) -> dict:
    """
    根据手机号获取或创建用户

    Args:
        phone: 手机号
        nickname: 昵称(可选)
        avatar: 头像URL(可选)

    Returns:
        用户信息字典 {"id": int, "phone": str, "nickname": str, "role": str, ...}
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. 查询数据库是否存在该手机号用户
        cursor.execute("""
            SELECT id, phone, nickname, avatar, role, status,
                   created_at, updated_at
            FROM users
            WHERE phone = ?
        """, (phone,))

        user = cursor.fetchone()

        if user:
            # 2. 如果存在,返回用户信息
            business_logger.info(f"用户已存在: phone={phone}, user_id={user['id']}")
            return {
                'id': user['id'],
                'phone': user['phone'],
                'nickname': user['nickname'],
                'avatar': user['avatar'],
                'role': user['role'],
                'status': user['status'],
                'created_at': user['created_at'],
                'updated_at': user['updated_at']
            }
        else:
            # 3. 如果不存在,创建新用户
            if not nickname:
                nickname = f"用户{phone[-4:]}"

            cursor.execute("""
                INSERT INTO users (phone, nickname, avatar, role, status)
                VALUES (?, ?, ?, 'user', 'active')
            """, (phone, nickname, avatar))

            user_id = cursor.lastrowid
            conn.commit()

            business_logger.info(f"创建新用户成功: phone={phone}, user_id={user_id}, nickname={nickname}")

            return {
                'id': user_id,
                'phone': phone,
                'nickname': nickname,
                'avatar': avatar,
                'role': 'user',
                'status': 'active',
                'created_at': None,
                'updated_at': None
            }

    except Exception as e:
        conn.rollback()
        business_logger.error(f"获取或创建用户失败: phone={phone}, error={str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    """
    根据用户ID获取用户信息

    Args:
        user_id: 用户ID

    Returns:
        用户信息字典 或 None
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, phone, nickname, avatar, role, status,
                   created_at, updated_at
            FROM users
            WHERE id = ?
        """, (user_id,))

        user = cursor.fetchone()

        if user:
            business_logger.info(f"查询用户成功: user_id={user_id}, phone={user['phone']}")
            return {
                'id': user['id'],
                'phone': user['phone'],
                'nickname': user['nickname'],
                'avatar': user['avatar'],
                'role': user['role'],
                'status': user['status'],
                'created_at': user['created_at'],
                'updated_at': user['updated_at']
            }
        else:
            business_logger.warning(f"用户不存在: user_id={user_id}")
            return None

    except Exception as e:
        business_logger.error(f"查询用户失败: user_id={user_id}, error={str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()
