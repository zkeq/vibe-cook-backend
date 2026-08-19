#!/usr/bin/env python3
# coding: utf-8
"""
使用 GPT 图像生成 API 为菜谱生成标准化示意图

功能：
1. 读取菜谱数据和 markdown 原文
2. 使用 GPT 图像生成 API 生成食物示意图
3. 上传到腾讯云 COS
4. 更新数据库
"""

import os
import sys
import json
import sqlite3
import requests
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional
from qcloud_cos import CosConfig, CosS3Client
from logger import business_logger
from pipeline_env import (
    IMAGE_API_URL as API_URL,
    CHATFIRE_IMAGE_MODEL as IMAGE_MODEL,
    COS_BUCKET,
    COS_REGION,
    COS_PUBLIC_BASE_URL,
    require_chatfire_key,
    require_cos,
)

COS_FOLDER_PREFIX = "/cook/ai-generated/"

# 配置
DB_PATH = "data/vibe_cook.db"
HOWTOCOOK_DIR = Path("../HowToCook-official/dishes")
MAX_WORKERS = 6
TEST_MODE = False  # 先测试一张
OVERWRITE_EXISTING = True  # 是否覆盖已有的封面图


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_cos_client():
    """创建 COS 客户端"""
    secret_id, secret_key = require_cos()
    config = CosConfig(
        Region=COS_REGION,
        SecretId=secret_id,
        SecretKey=secret_key,
    )
    return CosS3Client(config)


def find_markdown_file(recipe_id: str, recipe_title: str) -> Optional[Path]:
    """查找菜谱对应的 markdown 文件"""
    # 遍历所有分类目录
    for category_dir in HOWTOCOOK_DIR.iterdir():
        if not category_dir.is_dir() or category_dir.name == "template":
            continue

        # 遍历菜谱目录
        for recipe_dir in category_dir.iterdir():
            if not recipe_dir.is_dir():
                continue

            # 查找 .md 文件
            md_files = list(recipe_dir.glob("*.md"))
            if md_files:
                # 检查标题是否匹配
                md_file = md_files[0]
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if recipe_title in content or recipe_dir.name == recipe_title:
                        return md_file

    return None


def generate_food_image(recipe_data: Dict[str, Any], md_content: str = None) -> Optional[str]:
    """
    使用 GPT 生成菜谱示意图

    Args:
        recipe_data: 菜谱数据
        md_content: markdown 原文（可选）

    Returns:
        生成的图片 URL
    """
    title = recipe_data.get('title', '')
    summary = recipe_data.get('summary', '')
    category = recipe_data.get('category', '')

    # 构建 prompt
    prompt = f"""请生成一张专业的美食摄影照片：

菜品名称：{title}
分类：{category}
简介：{summary}

要求：
1. 高清美食摄影风格
2. 自然光线，色彩鲜艳
3. 白色餐具，干净背景
4. 俯视或45度角拍摄
5. 突出食材质感和色泽
6. 专业摆盘，有食欲感

请生成一张真实的、让人有食欲的菜品照片。"""

    # 如果有 markdown，补充细节
    if md_content:
        # 提取主要食材
        if "必备原料" in md_content or "食材" in md_content:
            prompt += "\n\n食材细节：从 markdown 中提取的食材信息"

    try:
        headers = {
            "Authorization": f"Bearer {require_chatfire_key()}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024"
        }

        business_logger.info(f"  正在生成图片...")
        response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        data = response.json()
        if data.get('data') and len(data['data']) > 0:
            image_url = data['data'][0].get('url')
            business_logger.info(f"  ✓ 图片生成成功")
            return image_url
        else:
            business_logger.error(f"  ✗ API 返回数据格式错误")
            return None

    except Exception as e:
        business_logger.error(f"  ✗ 生成图片失败: {e}")
        return None


def download_image(url: str) -> Optional[bytes]:
    """下载图片"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        business_logger.error(f"下载图片失败: {e}")
        return None


def upload_to_cos(cos_client: CosS3Client, image_data: bytes, recipe_id: str) -> Optional[str]:
    """上传图片到 COS"""
    try:
        cos_key = f"{COS_FOLDER_PREFIX}{recipe_id}.jpg"

        cos_client.put_object(
            Bucket=COS_BUCKET,
            Body=image_data,
            Key=cos_key,
            EnableMD5=False
        )

        url = f"{COS_PUBLIC_BASE_URL}{cos_key}"
        business_logger.info(f"  ✓ 上传到 COS: {url}")
        return url

    except Exception as e:
        business_logger.error(f"  ✗ 上传 COS 失败: {e}")
        return None


def process_recipe(recipe_row, cos_client: CosS3Client) -> bool:
    """处理单个菜谱"""
    try:
        recipe_id = recipe_row['id']
        recipe_data = json.loads(recipe_row['data'])
        title = recipe_data.get('title', '')

        business_logger.info(f"\n处理菜谱: {title} (ID: {recipe_id})")

        # 检查是否已有 cover_image
        if recipe_data.get('cover_image') and not OVERWRITE_EXISTING:
            business_logger.info(f"  跳过（已有封面图）")
            return True

        # 查找 markdown 文件
        md_file = find_markdown_file(recipe_id, title)
        md_content = None
        if md_file:
            business_logger.info(f"  找到 markdown: {md_file.name}")
            with open(md_file, 'r', encoding='utf-8') as f:
                md_content = f.read()

        # 生成图片
        generated_url = generate_food_image(recipe_data, md_content)
        if not generated_url:
            return False

        # 下载图片
        image_data = download_image(generated_url)
        if not image_data:
            return False

        # 上传到 COS
        cos_url = upload_to_cos(cos_client, image_data, recipe_id)
        if not cos_url:
            return False

        # 更新数据库 - 只设置 cover_image
        conn = get_db_connection()
        cursor = conn.cursor()

        recipe_data['cover_image'] = cos_url

        cursor.execute("""
            UPDATE recipes
            SET cover_image = ?, data = ?
            WHERE id = ?
        """, (cos_url, json.dumps(recipe_data, ensure_ascii=False), recipe_id))

        conn.commit()
        cursor.close()
        conn.close()

        business_logger.info(f"  ✓ 已更新数据库 (cover_image)")
        return True

    except Exception as e:
        business_logger.error(f"处理失败: {e}")
        return False


def main():
    business_logger.info("=" * 60)
    business_logger.info("开始使用 AI 生成菜谱示意图")
    business_logger.info("=" * 60)

    # 创建 COS 客户端
    cos_client = get_cos_client()

    # 获取所有菜谱
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, data, cover_image
        FROM recipes
        WHERE status = 'published'
        ORDER BY id
    """)

    recipes = cursor.fetchall()
    cursor.close()
    conn.close()

    business_logger.info(f"共 {len(recipes)} 个菜谱")

    if TEST_MODE:
        business_logger.info("【测试模式】仅处理第一个菜谱")
        recipes = recipes[:1]

    # 处理
    success_count = 0
    failed_count = 0

    if TEST_MODE:
        # 测试模式：单线程
        for recipe in recipes:
            if process_recipe(recipe, cos_client):
                success_count += 1
            else:
                failed_count += 1
    else:
        # 生产模式：并发处理
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_recipe, recipe, cos_client): recipe for recipe in recipes}

            for future in as_completed(futures):
                if future.result():
                    success_count += 1
                else:
                    failed_count += 1

                processed = success_count + failed_count
                print(f"\r进度: {processed}/{len(recipes)} (✅{success_count} ❌{failed_count})", end="")

    # 汇总
    business_logger.info(f"\n\n{'=' * 60}")
    business_logger.info(f"完成！")
    business_logger.info(f"✅ 成功: {success_count}")
    business_logger.info(f"❌ 失败: {failed_count}")
    business_logger.info("=" * 60)


if __name__ == "__main__":
    main()
