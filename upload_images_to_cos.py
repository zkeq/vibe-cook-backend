#!/usr/bin/env python3
# coding: utf-8
"""
上传 HowToCook 图片到腾讯云 COS

功能：
1. 遍历 HowToCook 的图片文件
2. 上传到腾讯云 COS
3. 记录图片 URL
4. 更新数据库中的菜谱数据
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from qcloud_cos import CosConfig, CosS3Client
from logger import business_logger
from pipeline_env import (
    COS_BUCKET,
    COS_REGION,
    COS_PUBLIC_BASE_URL,
    require_cos,
)

COS_FOLDER_PREFIX = "/cook/"

# 路径配置
HOWTOCOOK_DIR = Path("../HowToCook-official/dishes")
DB_PATH = "data/vibe_cook.db"


def get_cos_client():
    """创建 COS 客户端"""
    secret_id, secret_key = require_cos()
    config = CosConfig(
        Region=COS_REGION,
        SecretId=secret_id,
        SecretKey=secret_key,
    )
    return CosS3Client(config)


def upload_image_to_cos(client: CosS3Client, local_path: Path, cos_key: str) -> str:
    """
    上传图片到 COS

    Args:
        client: COS 客户端
        local_path: 本地文件路径
        cos_key: COS 对象键（不含 bucket）

    Returns:
        图片的公网 URL
    """
    try:
        with open(local_path, 'rb') as f:
            client.put_object(
                Bucket=COS_BUCKET,
                Body=f,
                Key=cos_key,
                EnableMD5=False
            )

        # 构建公网 URL
        url = f"{COS_PUBLIC_BASE_URL}{cos_key}"
        business_logger.info(f"✓ 上传成功: {local_path.name} -> {url}")
        return url

    except Exception as e:
        business_logger.error(f"✗ 上传失败: {local_path} - {e}")
        return ""


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def find_recipe_images(dishes_dir: Path) -> Dict[str, List[Dict[str, str]]]:
    """
    查找所有菜谱的图片

    Returns:
        {
            "菜谱目录名": [
                {"local_path": "...", "filename": "1.jpeg", "category": "..."},
                ...
            ]
        }
    """
    recipe_images = {}

    for category_dir in dishes_dir.iterdir():
        if not category_dir.is_dir() or category_dir.name == "template":
            continue

        for recipe_dir in category_dir.iterdir():
            if not recipe_dir.is_dir():
                continue

            recipe_dir_name = recipe_dir.name
            images = []

            for img_file in recipe_dir.iterdir():
                if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
                    images.append({
                        "local_path": str(img_file),
                        "filename": img_file.name,
                        "category": category_dir.name,
                        "recipe_dir": recipe_dir_name
                    })

            if images:
                recipe_images[recipe_dir_name] = images

    return recipe_images


def match_recipe_in_db(cursor, recipe_dir_name: str, category: str):
    """
    在数据库中查找匹配的菜谱

    尝试多种匹配方式：
    1. 精确匹配 title
    2. 模糊匹配 title
    3. 通过分类 + 拼音ID 匹配
    """
    # 方式1：精确匹配 title
    cursor.execute("""
        SELECT id, data FROM recipes
        WHERE json_extract(data, '$.title') = ?
    """, (recipe_dir_name,))

    result = cursor.fetchone()
    if result:
        return result

    # 方式2：模糊匹配
    cursor.execute("""
        SELECT id, data FROM recipes
        WHERE json_extract(data, '$.title') LIKE ?
    """, (f'%{recipe_dir_name}%',))

    result = cursor.fetchone()
    if result:
        return result

    # 方式3：通过ID匹配（category + 拼音）
    from pypinyin import lazy_pinyin
    pinyin_str = "-".join(lazy_pinyin(recipe_dir_name)).lower()

    # 分类映射
    category_map = {
        "vegetable_dish": "素菜",
        "meat_dish": "荤菜",
        "aquatic": "水产",
        "breakfast": "早餐",
        "staple": "主食",
        "semi-finished": "半成品加工",
        "soup": "汤",
        "drink": "饮料",
        "dessert": "甜品",
        "condiment": "酱料"
    }

    category_en = None
    for en, cn in category_map.items():
        if category == cn or category == en:
            category_en = en
            break

    if category_en:
        recipe_id_pattern = f"{category_en}_{pinyin_str}%"
        cursor.execute("""
            SELECT id, data FROM recipes
            WHERE id LIKE ?
        """, (recipe_id_pattern,))

        result = cursor.fetchone()
        if result:
            return result

    return None


def main():
    business_logger.info("=" * 60)
    business_logger.info("开始上传图片到腾讯云 COS")
    business_logger.info("=" * 60)

    # 1. 创建 COS 客户端
    cos_client = get_cos_client()
    business_logger.info("✓ COS 客户端已创建")

    # 2. 查找所有图片
    recipe_images = find_recipe_images(HOWTOCOOK_DIR)
    total_recipes = len(recipe_images)
    total_images = sum(len(imgs) for imgs in recipe_images.values())

    business_logger.info(f"找到 {total_recipes} 个菜谱，共 {total_images} 张图片")

    # 3. 上传图片并记录 URL
    conn = get_db_connection()
    cursor = conn.cursor()

    uploaded_count = 0
    failed_count = 0

    for recipe_dir_name, images in recipe_images.items():
        business_logger.info(f"\n处理菜谱目录: {recipe_dir_name} ({len(images)} 张图片)")

        category = images[0]["category"]

        # 在数据库中查找匹配的菜谱
        recipe_row = match_recipe_in_db(cursor, recipe_dir_name, category)

        if not recipe_row:
            business_logger.warning(f"  ! 数据库中未找到匹配的菜谱: {recipe_dir_name}")
            continue

        recipe_id = recipe_row["id"]
        recipe_data = json.loads(recipe_row["data"])
        business_logger.info(f"  匹配到菜谱: {recipe_data.get('title')} (ID: {recipe_id})")

        # 上传图片
        image_urls = []
        for img in images:
            local_path = Path(img["local_path"])
            filename = img["filename"]

            # COS 路径: /cook/{category}/{recipe_dir_name}/{filename}
            cos_key = f"{COS_FOLDER_PREFIX}{category}/{recipe_dir_name}/{filename}"

            # 上传
            url = upload_image_to_cos(cos_client, local_path, cos_key)
            if url:
                image_urls.append(url)
                uploaded_count += 1
            else:
                failed_count += 1

        # 更新数据库：设置封面图
        if image_urls:
            recipe_data["cover_image"] = image_urls[0]
            if len(image_urls) > 1:
                recipe_data["overview_image"] = image_urls[1]

            # 保存
            cursor.execute("""
                UPDATE recipes
                SET cover_image = ?, data = ?
                WHERE id = ?
            """, (image_urls[0], json.dumps(recipe_data, ensure_ascii=False), recipe_id))

            conn.commit()
            business_logger.info(f"  ✓ 已更新菜谱: {recipe_data.get('title')}")

    cursor.close()
    conn.close()

    # 4. 汇总
    business_logger.info(f"\n{'=' * 60}")
    business_logger.info(f"上传完成！")
    business_logger.info(f"✅ 成功: {uploaded_count}")
    business_logger.info(f"❌ 失败: {failed_count}")
    business_logger.info(f"📊 总计: {total_images}")
    business_logger.info("=" * 60)


if __name__ == "__main__":
    main()
