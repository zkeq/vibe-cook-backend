"""
菜谱业务逻辑
遵循 business/user.py 的模板模式
使用 SQLite 语法
"""
import json
from typing import Optional, List, Dict, Any
from db import get_db_connection
from logger import business_logger

def list_recipes(
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """获取菜谱列表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        where_clauses = ["status = 'published'"]
        params = []

        if category:
            where_clauses.append("category = ?")
            params.append(category)

        if search:
            where_clauses.append("(title LIKE ? OR data LIKE ?)")
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])

        where_sql = " AND ".join(where_clauses)

        # 查询总数
        count_sql = f"SELECT COUNT(*) as total FROM recipes WHERE {where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()["total"]

        # 查询列表
        offset = (page - 1) * limit
        list_sql = f"""
            SELECT id, data
            FROM recipes
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(list_sql, params + [limit, offset])
        rows = cursor.fetchall()

        # 解析 JSON 数据
        recipes = []
        for row in rows:
            try:
                full_data = json.loads(row["data"])
                summary = {
                    "id": full_data.get("id"),
                    "title": full_data.get("title"),
                    "summary": full_data.get("summary", ""),
                    "category": full_data.get("category"),
                    "difficulty": full_data.get("difficulty"),
                    "duration_min": full_data.get("duration_min"),
                    "calories": full_data.get("calories"),
                    "cover_image": full_data.get("cover_image", ""),
                    "tags": full_data.get("tags", []),
                    "steps_count": len(full_data.get("steps", [])),
                }
                recipes.append(summary)
            except json.JSONDecodeError as e:
                business_logger.error(f"Failed to parse recipe: id={row['id']}, error={e}")
                continue

        return {
            "data": recipes,
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        business_logger.error(f"list_recipes failed: error={e}")
        raise
    finally:
        cursor.close()
        conn.close()


def get_recipe_by_id(recipe_id: str) -> Optional[Dict[str, Any]]:
    """根据 ID 获取菜谱详情"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        sql = "SELECT data FROM recipes WHERE id = ? AND status = 'published'"
        cursor.execute(sql, (recipe_id,))
        row = cursor.fetchone()

        if not row:
            return None

        try:
            return json.loads(row["data"])
        except json.JSONDecodeError as e:
            business_logger.error(f"Failed to parse recipe: id={recipe_id}, error={e}")
            return None
    except Exception as e:
        business_logger.error(f"get_recipe_by_id failed: id={recipe_id}, error={e}")
        raise
    finally:
        cursor.close()
        conn.close()


def search_recipes(query: str) -> List[Dict[str, Any]]:
    """搜索菜谱"""
    result = list_recipes(search=query, page=1, limit=50)
    return result["data"]


def get_recipes_by_category(category: str) -> List[Dict[str, Any]]:
    """根据分类获取菜谱"""
    result = list_recipes(category=category, page=1, limit=100)
    return result["data"]


def create_recipe(recipe_data: Dict[str, Any]) -> str:
    """创建/更新菜谱（供导入脚本使用）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        recipe_id = recipe_data["id"]
        title = recipe_data["title"]
        category = recipe_data.get("category", "")
        cover_image = recipe_data.get("cover_image", "")
        data_json = json.dumps(recipe_data, ensure_ascii=False)

        # SQLite 使用 INSERT OR REPLACE
        sql = """
            INSERT OR REPLACE INTO recipes (id, title, category, cover_image, data, status)
            VALUES (?, ?, ?, ?, ?, 'published')
        """
        cursor.execute(sql, (recipe_id, title, category, cover_image, data_json))
        conn.commit()

        business_logger.info(f"Recipe saved: id={recipe_id}, title={title}")
        return recipe_id
    except Exception as e:
        conn.rollback()
        business_logger.error(f"create_recipe failed: error={e}")
        raise
    finally:
        cursor.close()
        conn.close()


def get_random_recipes(limit: int = 24) -> List[Dict[str, Any]]:
    """
    随机获取菜谱

    Args:
        limit: 返回数量

    Returns:
        随机菜谱列表
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT id, data
            FROM recipes
            WHERE status = 'published'
            ORDER BY RANDOM()
            LIMIT ?
        """
        cursor.execute(sql, (limit,))
        rows = cursor.fetchall()

        recipes = []
        for row in rows:
            try:
                full_data = json.loads(row["data"])
                summary = {
                    "id": full_data.get("id"),
                    "title": full_data.get("title"),
                    "summary": full_data.get("summary", ""),
                    "category": full_data.get("category"),
                    "difficulty": full_data.get("difficulty"),
                    "duration_min": full_data.get("duration_min"),
                    "calories": full_data.get("calories"),
                    "cover_image": full_data.get("cover_image", ""),
                    "tags": full_data.get("tags", []),
                    "steps_count": len(full_data.get("steps", [])),
                }
                recipes.append(summary)
            except json.JSONDecodeError as e:
                business_logger.error(f"Failed to parse recipe: id={row['id']}, error={e}")
                continue

        return recipes
    except Exception as e:
        business_logger.error(f"get_random_recipes failed: error={e}")
        raise
    finally:
        cursor.close()
        conn.close()


def get_recipe_stats() -> Dict[str, Any]:
    """
    获取菜谱统计信息

    Returns:
        {
            "total": 总数,
            "avg_steps": 平均步数
        }
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 获取总数
        cursor.execute("SELECT COUNT(*) as total FROM recipes WHERE status = 'published'")
        total = cursor.fetchone()["total"]

        # 计算平均步数
        cursor.execute("""
            SELECT data FROM recipes WHERE status = 'published'
        """)
        rows = cursor.fetchall()

        total_steps = 0
        valid_count = 0
        for row in rows:
            try:
                full_data = json.loads(row["data"])
                steps = full_data.get("steps", [])
                if steps:
                    total_steps += len(steps)
                    valid_count += 1
            except:
                continue

        avg_steps = round(total_steps / valid_count) if valid_count > 0 else 5

        return {
            "total": total,
            "avg_steps": avg_steps
        }
    except Exception as e:
        business_logger.error(f"get_recipe_stats failed: error={e}")
        raise
    finally:
        cursor.close()
        conn.close()


def get_categories() -> List[str]:
    """
    获取所有分类列表

    Returns:
        分类名称列表
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT DISTINCT category
            FROM recipes
            WHERE status = 'published' AND category != ''
            ORDER BY category
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [row["category"] for row in rows]
    except Exception as e:
        business_logger.error(f"get_categories failed: error={e}")
        raise
    finally:
        cursor.close()
        conn.close()


def get_recipe_page_number(recipe_id: str, category: Optional[str] = None, limit: int = 24) -> Optional[int]:
    """
    获取菜谱在列表中的页码

    Args:
        recipe_id: 菜谱 ID
        category: 分类筛选
        limit: 每页数量

    Returns:
        页码（从1开始），如果找不到返回 None
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 构建查询条件
        where_conditions = ["status = 'published'"]
        params = []

        if category:
            where_conditions.append("category = ?")
            params.append(category)

        where_clause = " AND ".join(where_conditions)

        # 获取所有菜谱ID（按创建时间倒序）
        sql = f"""
            SELECT id
            FROM recipes
            WHERE {where_clause}
            ORDER BY created_at DESC
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # 找到目标菜谱的位置
        for index, row in enumerate(rows):
            if row["id"] == recipe_id:
                # 计算页码（从1开始）
                page = (index // limit) + 1
                return page

        return None
    except Exception as e:
        business_logger.error(f"get_recipe_page_number failed: error={e}")
        return None
    finally:
        cursor.close()
        conn.close()
