# coding: utf-8
"""
业务逻辑模块 - 统一导出接口
将所有业务逻辑函数从子模块导出,保持向后兼容
"""

# 用户管理
from .user import (
    get_or_create_user_by_phone,
    get_user_by_id
)

# 菜谱管理
from .recipe import (
    list_recipes,
    get_recipe_by_id,
    search_recipes,
    get_recipes_by_category,
    create_recipe,
    get_random_recipes,
    get_recipe_stats,
    get_categories,
    get_recipe_page_number
)

__all__ = [
    # 用户管理
    'get_or_create_user_by_phone',
    'get_user_by_id',
    # 菜谱管理
    'list_recipes',
    'get_recipe_by_id',
    'search_recipes',
    'get_recipes_by_category',
    'create_recipe',
    'get_random_recipes',
    'get_recipe_stats',
    'get_categories',
    'get_recipe_page_number',
]
