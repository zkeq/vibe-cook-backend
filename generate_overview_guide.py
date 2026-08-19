#!/usr/bin/env python3
# coding: utf-8
"""
使用 GPT 图像生成 API 为菜谱生成全解图（制作步骤指南图）

功能：
1. 读取菜谱完整步骤和食材
2. 使用 GPT 图像生成 API 生成步骤指南图（类似螺蛳粉包装背面）
3. 上传到腾讯云 COS
4. 更新数据库的 overview_image 字段
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
from pypinyin import lazy_pinyin
from pipeline_env import (
    IMAGE_API_URL as API_URL,
    CHATFIRE_IMAGE_MODEL as IMAGE_MODEL,
    COS_BUCKET,
    COS_REGION,
    COS_PUBLIC_BASE_URL,
    require_chatfire_key,
    require_cos,
)

COS_FOLDER_PREFIX = "/cook/overview/"

# 配置
DB_PATH = "data/vibe_cook.db"
HOWTOCOOK_DIR = Path("../HowToCook-official/dishes")
MAX_WORKERS = 24
TEST_MODE = False  # 先测试一张
OVERWRITE_EXISTING = True  # 是否覆盖已有的全解图


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
    """
    查找菜谱对应的 markdown 文件
    ID 包含文件名拼音即可
    """
    # 所有分类目录
    categories = ["vegetable_dish", "meat_dish", "aquatic", "breakfast", "staple",
                  "semi-finished", "soup", "drink", "dessert", "condiment"]

    # 遍历所有分类
    for category in categories:
        category_path = HOWTOCOOK_DIR / category
        if not category_path.exists():
            continue

        # 遍历该分类下的所有文件和目录
        for item in category_path.iterdir():
            # 情况1：直接是 .md 文件
            if item.is_file() and item.suffix == '.md':
                file_pinyin = '-'.join(lazy_pinyin(item.stem)).lower()
                # ID 包含文件名拼音
                if file_pinyin in recipe_id:
                    return item

            # 情况2：目录
            elif item.is_dir():
                # 先检查目录名
                dir_pinyin = '-'.join(lazy_pinyin(item.name)).lower()
                if dir_pinyin in recipe_id:
                    md_files = list(item.glob("*.md"))
                    if md_files:
                        return md_files[0]

                # 再检查目录下的 md 文件
                for md_file in item.glob("*.md"):
                    file_pinyin = '-'.join(lazy_pinyin(md_file.stem)).lower()
                    if file_pinyin in recipe_id:
                        return md_file

    return None


def generate_overview_guide(recipe_data: Dict[str, Any], md_content: str = None) -> Optional[str]:
    """
    使用 GPT 生成菜谱全解图（步骤指南图）

    Args:
        recipe_data: 菜谱数据
        md_content: markdown 原文（可选）

    Returns:
        生成的图片 URL
    """
    title = recipe_data.get('title', '')

    # 如果有 markdown 原文，直接使用
    if md_content:
        prompt = f"""将这个做饭教程做成一张全解图，类似于螺蛳粉背面的制作指南一样，让人一眼就能看懂并且愿意去做，为我生成

菜品名称：{title}

{md_content}

请生成一张完整的、可视化的制作步骤指南图。"""
    else:
        # 降级：使用数据库中的数据
        ingredients = recipe_data.get('ingredients', [])
        steps = recipe_data.get('steps', [])

        # 构建食材列表（所有食材）
        ingredients_text = "主要食材：\n"
        for ing in ingredients:
            name = ing.get('name', '')
            amount = ing.get('amount', '')
            ingredients_text += f"• {name} {amount}\n"

        # 构建步骤列表（所有步骤）
        steps_text = "制作步骤：\n"
        for i, step in enumerate(steps, 1):
            instruction = step.get('instruction', '')
            steps_text += f"{i}. {instruction}\n"

        prompt = f"""将这个做饭教程做成一张全解图，类似于螺蛳粉背面的制作指南一样，让人一眼就能看懂并且愿意去做，为我生成

菜品名称：{title}

{ingredients_text}

{steps_text}

请生成一张完整的、可视化的制作步骤指南图。"""

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

    # 无限重试直到成功
    retry_count = 0
    while True:
        try:
            if retry_count > 0:
                business_logger.info(f"  重试第 {retry_count} 次...")
            else:
                business_logger.info(f"  正在生成全解图...")

            response = requests.post(API_URL, headers=headers, json=payload, timeout=3600)
            response.raise_for_status()

            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                image_url = data['data'][0].get('url')
                if retry_count > 0:
                    business_logger.info(f"  ✓ 重试成功！")
                else:
                    business_logger.info(f"  ✓ 全解图生成成功")
                return image_url
            else:
                business_logger.error(f"  ✗ API 返回数据格式错误，等待 3 秒后重试...")
                time.sleep(3)
                retry_count += 1

        except requests.exceptions.Timeout:
            business_logger.error(f"  ✗ 请求超时，等待 5 秒后重试...")
            time.sleep(5)
            retry_count += 1
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 502:
                business_logger.error(f"  ✗ 502 Bad Gateway，等待 3 秒后重试...")
                time.sleep(3)
            else:
                business_logger.error(f"  ✗ HTTP 错误 {e.response.status_code}，等待 5 秒后重试...")
                time.sleep(5)
            retry_count += 1
        except Exception as e:
            business_logger.error(f"  ✗ 生成失败: {e}，等待 5 秒后重试...")
            time.sleep(5)
            retry_count += 1


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
        cos_key = f"{COS_FOLDER_PREFIX}{recipe_id}_overview.jpg"

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

        # 检查是否已有 overview_image
        if recipe_data.get('overview_image') and not OVERWRITE_EXISTING:
            business_logger.info(f"  跳过（已有全解图）")
            return True

        # 查找 markdown 文件
        md_file = find_markdown_file(recipe_id, title)
        md_content = None
        if md_file:
            business_logger.info(f"  找到 markdown: {md_file.name}")
            with open(md_file, 'r', encoding='utf-8') as f:
                md_content = f.read()

        # 生成全解图
        generated_url = generate_overview_guide(recipe_data, md_content)
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

        # 更新数据库
        conn = get_db_connection()
        cursor = conn.cursor()

        recipe_data['overview_image'] = cos_url

        cursor.execute("""
            UPDATE recipes
            SET data = ?
            WHERE id = ?
        """, (json.dumps(recipe_data, ensure_ascii=False), recipe_id))

        conn.commit()
        cursor.close()
        conn.close()

        business_logger.info(f"  ✓ 已更新数据库 (overview_image)")
        return True

    except Exception as e:
        business_logger.error(f"处理失败: {e}")
        return False


def main():
    business_logger.info("=" * 60)
    business_logger.info("开始生成菜谱全解图（步骤指南图）")
    business_logger.info("=" * 60)

    # 创建 COS 客户端
    cos_client = get_cos_client()

    # 获取所有菜谱
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, data
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
