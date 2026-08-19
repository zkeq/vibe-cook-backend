# coding: utf-8
"""
食谱路由冒烟测试

验证:
- 后端可正常 import(SQLite 自动建表,零外部依赖)
- 公开列表/详情路由可用
- 写入路由需要 editor 权限(未带 token 应被拒)
- editor 登录后可写入,并能查回
"""

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

SAMPLE = {
    "id": "test-dish",
    "title": "测试菜",
    "category": "vegetable_dish",
    "cover_image": "/static/recipes/test/cover.jpg",
    "summary": "一道用于测试的菜",
    "difficulty": 1,
    "calories": 100,
    "duration_min": 5,
    "tags": ["测试"],
    "steps": [{"index": 1, "title": "第一步", "instruction": "做点什么"}],
}


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_list_recipes_public():
    resp = client.get("/api/v1/recipes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["recipes"], list)


def test_upsert_requires_auth():
    resp = client.post("/api/v1/recipes", json={"data": SAMPLE})
    assert resp.status_code in (401, 403)


def test_upsert_and_get_with_editor():
    # admin 账号(SQLite 初始化时创建)登录拿 token
    login = client.post(
        "/api/v1/auth/login-by-password",
        json={"phone": "admin", "password": "admin123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 写入
    up = client.post("/api/v1/recipes", json={"data": SAMPLE}, headers=headers)
    assert up.status_code == 200, up.text
    assert up.json()["recipe"]["id"] == "test-dish"

    # 查回详情
    got = client.get("/api/v1/recipes/test-dish")
    assert got.status_code == 200
    recipe = got.json()["recipe"]
    assert recipe["title"] == "测试菜"
    assert recipe["steps"][0]["title"] == "第一步"
