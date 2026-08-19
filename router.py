# coding: utf-8
"""
路由定义模块
所有API路由都在这里定义
每个路由只负责参数验证和调用business层函数
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import auth
import business
from db import get_db_connection
from logger import api_logger


# 创建路由器
api = APIRouter()


# ==================== Pydantic模型定义 ====================

class SendSMSRequest(BaseModel):
    phone: str = Field(..., description="手机号")


class LoginBySMSRequest(BaseModel):
    phone: str = Field(..., description="手机号")
    code: str = Field(..., description="验证码")


class LoginByPasswordRequest(BaseModel):
    phone: str = Field(..., description="账号(手机号或用户名)")
    password: str = Field(..., description="密码")


class UpsertRecipeRequest(BaseModel):
    """写入/更新食谱(完整结构化数据，契约见前端 lib/types.ts)"""
    data: dict = Field(..., description="完整结构化食谱(Recipe 契约)，须含 id / title")


# ==================== 响应模型定义 ====================

class LoginResponse(BaseModel):
    """登录响应"""
    success: bool
    token: str
    user: dict


# ==================== 认证相关路由 ====================

@api.post("/auth/login-by-password", response_model=LoginResponse)
async def login_by_password(req: LoginByPasswordRequest):
    """密码登录(管理员/编辑)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, phone, password, nickname, avatar, role, status
            FROM users WHERE phone = ?
        """, (req.phone,))
        user = cursor.fetchone()

        if not user or not user['password']:
            raise HTTPException(status_code=400, detail="账号或密码错误")
        if user['status'] != 'active':
            raise HTTPException(status_code=403, detail="账号已被禁用")
        if not auth.verify_password(req.password, user['password']):
            raise HTTPException(status_code=400, detail="账号或密码错误")

        token = auth.create_token(user['id'], user['phone'], user['role'])
        user.pop('password', None)
        return {"success": True, "token": token, "user": user}
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"密码登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@api.post("/auth/send-sms")
async def send_sms_code(req: SendSMSRequest):
    """发送短信验证码"""
    try:
        result = auth.send_sms_code(req.phone)
        return {"success": result["success"], "message": result["message"], "code": result.get("code")}
    except Exception as e:
        api_logger.error(f"发送短信失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.post("/auth/login-by-sms", response_model=LoginResponse)
async def login_by_sms(req: LoginBySMSRequest):
    """短信验证码登录"""
    try:
        # 1. 验证验证码
        if not auth.verify_sms_code(req.phone, req.code):
            raise HTTPException(status_code=400, detail="验证码错误或已过期")

        # 2. 获取或创建用户
        user = business.get_or_create_user_by_phone(req.phone)

        # 3. 生成token
        token = auth.create_token(user['id'], user['phone'], user['role'])

        return {"success": True, "token": token, "user": user}
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"短信登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/auth/profile")
async def get_profile(user: dict = Depends(auth.get_current_user)):
    """获取当前用户信息"""
    try:
        user_info = business.get_user_by_id(user['user_id'])
        if not user_info:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"success": True, "user": user_info}
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"获取用户信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 食谱相关路由 ====================

@api.get("/recipes")
async def list_recipes_endpoint(
    category: str = None,
    search: str = None,
    page: int = 1,
    limit: int = 20
):
    """获取食谱列表(公开)"""
    try:
        result = business.list_recipes(
            category=category,
            search=search,
            page=page,
            limit=limit
        )
        return result
    except Exception as e:
        api_logger.error(f"获取食谱列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/recipes/search")
async def search_recipes_endpoint(q: str):
    """搜索食谱(公开)"""
    try:
        recipes = business.search_recipes(q)
        return {"data": recipes}
    except Exception as e:
        api_logger.error(f"搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/recipes/random")
async def get_random_recipes_endpoint(limit: int = 24):
    """随机获取食谱(公开)"""
    try:
        recipes = business.get_random_recipes(limit=limit)
        return {"data": recipes}
    except Exception as e:
        api_logger.error(f"随机获取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/recipes/stats")
async def get_recipe_stats_endpoint():
    """获取菜谱统计信息(公开)"""
    try:
        stats = business.get_recipe_stats()
        return stats
    except Exception as e:
        api_logger.error(f"获取统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/recipes/categories")
async def get_categories_endpoint():
    """获取所有分类列表(公开)"""
    try:
        categories = business.get_categories()
        return {"data": categories}
    except Exception as e:
        api_logger.error(f"获取分类失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/recipes/category/{category}")
async def get_recipes_by_category_endpoint(category: str):
    """根据分类获取食谱(公开)"""
    try:
        recipes = business.get_recipes_by_category(category)
        return {"data": recipes, "category": category}
    except Exception as e:
        api_logger.error(f"获取分类食谱失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/recipes/{recipe_id}")
async def get_recipe_endpoint(recipe_id: str):
    """获取菜谱详情(公开)"""
    try:
        recipe = business.get_recipe_by_id(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="食谱不存在")
        return recipe
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"获取食谱详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/recipes/{recipe_id}/page")
async def get_recipe_page_endpoint(recipe_id: str, category: str = None):
    """获取菜谱在列表中的页码(公开)"""
    try:
        page = business.get_recipe_page_number(recipe_id, category)
        if page is None:
            raise HTTPException(status_code=404, detail="食谱不存在")
        return {"page": page}
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"获取页码失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api.post("/recipes")
async def create_recipe_endpoint(
    req: UpsertRecipeRequest,
    user: dict = Depends(auth.require_editor),
):
    """创建/更新食谱(需要 editor/admin 权限)"""
    try:
        recipe_id = business.create_recipe(req.data)
        return {"success": True, "recipe_id": recipe_id}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"写入食谱失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
