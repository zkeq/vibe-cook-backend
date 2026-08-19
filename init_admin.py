#!/usr/bin/env python3
# coding: utf-8
"""
初始化管理员账号脚本
用于创建或重置管理员密码

使用方法:
    python init_admin.py
"""

import bcrypt
from db import get_db_connection

def hash_password(password: str) -> str:
    """使用bcrypt加密密码"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def create_or_update_admin():
    """创建或更新管理员账号"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查是否已存在admin用户
        cursor.execute("SELECT id, phone, nickname, role FROM users WHERE phone='admin'")
        admin = cursor.fetchone()

        # 默认密码
        default_password = "admin123"
        hashed_password = hash_password(default_password)

        if admin:
            # 更新现有管理员密码
            cursor.execute("""
                UPDATE users
                SET password=?, role='admin', status='active'
                WHERE phone='admin'
            """, (hashed_password,))
            conn.commit()
            print("\n✅ 管理员密码已重置！")
        else:
            # 创建新管理员
            cursor.execute("""
                INSERT INTO users (phone, password, nickname, role, status)
                VALUES ('admin', ?, '系统管理员', 'admin', 'active')
            """, (hashed_password,))
            conn.commit()
            print("\n✅ 管理员账号创建成功！")

        print("=" * 50)
        print("登录账号: admin")
        print(f"登录密码: {default_password}")
        print("=" * 50)
        print("⚠️  请登录后立即修改默认密码！")
        print()

        cursor.close()

    except Exception as e:
        print(f"\n❌ 操作失败: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("Vibe Cook Backend - 管理员账号初始化")
    print("=" * 50)
    create_or_update_admin()
