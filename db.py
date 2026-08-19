# coding: utf-8
"""
数据存储模块(SQLite 版)

小项目零外部依赖:
- 数据库: 单文件 SQLite,首次启动自动按 sql/init.sql 建表
- 短信验证码: 进程内内存存储(带 TTL),替代原来的 Redis

对外保持与原模板一致的接口:
- get_db_connection() / execute_query() / test_db_connection()
- r : 一个最小化的 KV 客户端(setex / get / delete),供 auth.py 使用
"""

import os
import time
import sqlite3
import threading
import yaml

# 读取配置
config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

# SQLite 文件路径(相对路径则相对于本文件目录)
_db_path = config['SQLITE']['path']
if not os.path.isabs(_db_path):
    _db_path = os.path.join(os.path.dirname(__file__), _db_path)
os.makedirs(os.path.dirname(_db_path), exist_ok=True)


def _dict_factory(cursor, row):
    """让查询结果以 dict 返回(支持 .get / .pop,与原 DictCursor 行为一致)"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_db_connection():
    """获取数据库连接(每次新建,SQLite 连接很轻量)"""
    conn = sqlite3.connect(_db_path, check_same_thread=False)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """首次启动时按 sql/init.sql 建表(幂等,表已存在则跳过)"""
    sql_path = os.path.join(os.path.dirname(__file__), 'sql', 'init.sql')
    if not os.path.exists(sql_path):
        return
    with open(sql_path, 'r', encoding='utf-8') as f:
        script = f.read()
    conn = get_db_connection()
    try:
        conn.executescript(script)
        conn.commit()
    finally:
        conn.close()


def execute_query(sql, params=None, fetch_one=False, fetch_all=False):
    """执行 SQL 的辅助函数(参数占位符用 ?)"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            conn.commit()
            result = cursor.rowcount
        cursor.close()
        return result
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def test_db_connection() -> bool:
    """测试数据库连接是否正常"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"数据库连接测试失败: {e}")
        return False


# ==================== 内存 KV 存储(替代 Redis,仅用于短信验证码) ====================

class _MemoryStore:
    """进程内带 TTL 的最小 KV 存储,接口对齐 redis 的 setex/get/delete。

    注意:数据存于内存,进程重启即清空;多 worker 不共享。
    对"短信验证码"这种短时效、单实例场景完全够用。
    """

    def __init__(self):
        self._data = {}            # key -> (value, expire_at | None)
        self._lock = threading.Lock()

    def setex(self, key, ttl_seconds, value):
        with self._lock:
            self._data[key] = (str(value), time.time() + ttl_seconds)

    def get(self, key):
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            value, expire_at = item
            if expire_at is not None and time.time() > expire_at:
                self._data.pop(key, None)
                return None
            return value

    def delete(self, key):
        with self._lock:
            self._data.pop(key, None)

    def ping(self) -> bool:
        return True


# 全局实例(供 auth.py: from db import r)
r = _MemoryStore()


# 模块导入时确保建表
init_db()

