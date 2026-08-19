#!/usr/bin/env python3
# coding: utf-8
"""
使用 GPT 图像生成 API 为每个菜谱步骤生成示意图

功能：
1. 读取菜谱每个步骤
2. 使用 GPT 图像生成 API 生成该步骤的操作示意图
3. 上传到腾讯云 COS /cook/steps/{recipe_id}/step_{index}.jpg
4. 更新数据库中步骤的 image 字段

使用方法:
    python3 generate_step_images.py --test  # 测试第一个菜谱的第一个步骤
    python3 generate_step_images.py         # 处理全部
"""

import os
import sys
import json
import sqlite3
import base64
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

COS_FOLDER_PREFIX = "/cook/steps/"

# 配置
DB_PATH = "data/vibe_cook.db"
MAX_WORKERS = 24
TEST_MODE = False  # 先测试一个菜谱的第一个步骤
OVERWRITE_EXISTING = False  # 是否覆盖已有步骤图


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_cos_client():
    secret_id, secret_key = require_cos()
    config = CosConfig(
        Region=COS_REGION,
        SecretId=secret_id,
        SecretKey=secret_key,
    )
    return CosS3Client(config)


def generate_step_image(recipe_title: str, step: Dict[str, Any]) -> Optional[bytes]:
    """
    使用 GPT 生成单个步骤的操作示意图

    Args:
        recipe_title: 菜谱标题
        step: 步骤数据

    Returns:
        生成的图片 bytes（直接从 b64_json 解码）
    """
    step_index = step.get('index', 0)
    step_title = step.get('title', f'步骤{step_index}')
    instruction = step.get('instruction', '')
    produces = step.get('produces', '')

    prompt = f"""请生成一张专业的烹饪步骤示意图：

菜品：{recipe_title}
步骤 {step_index}：{step_title}
操作说明：{instruction}
{f'本步产出：{produces}' if produces else ''}

要求：
1. 写实美食摄影风格
2. 清晰展示该步骤的操作动作或状态
3. 俯视或45度角拍摄
4. 干净整洁的厨房背景
5. 突出当前操作的关键细节
6. 光线充足，色彩自然
7. 让人一目了然这一步在做什么

请生成一张清晰直观的烹饪步骤示意图。"""

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
                business_logger.info(f"    重试第 {retry_count} 次...")
            else:
                business_logger.info(f"    正在生成步骤 {step_index} 图片...")

            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()

            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                # gpt-image-2 返回 b64_json，直接解码为 bytes
                image_b64 = data['data'][0].get('b64_json')
                if not image_b64:
                    business_logger.error(f"    ✗ API 返回数据中无 b64_json 字段，等待 3 秒后重试...")
                    time.sleep(3)
                    retry_count += 1
                    continue
                image_bytes = base64.b64decode(image_b64)
                if retry_count > 0:
                    business_logger.info(f"    ✓ 重试成功！")
                else:
                    business_logger.info(f"    ✓ 步骤 {step_index} 图片生成成功 ({len(image_bytes) // 1024}KB)")
                return image_bytes
            else:
                business_logger.error(f"    ✗ API 返回数据格式错误，等待 3 秒后重试...")
                time.sleep(3)
                retry_count += 1

        except requests.exceptions.Timeout:
            business_logger.error(f"    ✗ 请求超时，等待 5 秒后重试...")
            time.sleep(5)
            retry_count += 1
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 502:
                business_logger.error(f"    ✗ 502 Bad Gateway，等待 3 秒后重试...")
                time.sleep(3)
            else:
                business_logger.error(f"    ✗ HTTP 错误 {e.response.status_code}，等待 5 秒后重试...")
                time.sleep(5)
            retry_count += 1
        except Exception as e:
            business_logger.error(f"    ✗ 生成失败: {e}，等待 5 秒后重试...")
            time.sleep(5)
            retry_count += 1


def upload_to_cos(cos_client: CosS3Client, image_data: bytes, recipe_id: str, step_index: int) -> Optional[str]:
    try:
        cos_key = f"{COS_FOLDER_PREFIX}{recipe_id}/step_{step_index}.jpg"

        cos_client.put_object(
            Bucket=COS_BUCKET,
            Body=image_data,
            Key=cos_key,
            EnableMD5=False
        )

        url = f"{COS_PUBLIC_BASE_URL}{cos_key}"
        business_logger.info(f"    ✓ 上传到 COS: {url}")
        return url

    except Exception as e:
        business_logger.error(f"    ✗ 上传 COS 失败: {e}")
        return None


def process_recipe(recipe_row, cos_client: CosS3Client) -> int:
    """
    处理单个菜谱的所有步骤

    Returns:
        成功生成的步骤数
    """
    recipe_id = recipe_row['id']
    recipe_data = json.loads(recipe_row['data'])
    title = recipe_data.get('title', '')
    steps = recipe_data.get('steps', [])

    if not steps:
        business_logger.info(f"  ! {title} 没有步骤，跳过")
        return 0

    business_logger.info(f"\n处理菜谱: {title} (ID: {recipe_id}, {len(steps)} 个步骤)")

    if TEST_MODE:
        # 测试模式只处理第一个步骤
        steps = steps[:1]
        business_logger.info(f"  [测试模式] 只处理第一个步骤")

    success_count = 0

    for step in steps:
        step_index = step.get('index', 0)

        # 检查是否已有图片
        if step.get('image') and not OVERWRITE_EXISTING:
            business_logger.info(f"  步骤 {step_index} 已有图片，跳过")
            continue

        # 生成图片（直接返回 bytes）
        image_data = generate_step_image(title, step)
        if not image_data:
            continue

        # 上传到 COS
        cos_url = upload_to_cos(cos_client, image_data, recipe_id, step_index)
        if not cos_url:
            business_logger.error(f"  ✗ 步骤 {step_index} 图片上传失败")
            continue

        # 立刻写入数据库（每张生成后马上保存，防止中途失败丢失进度）
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 重新读取最新数据，避免并发覆盖
            cursor.execute("SELECT data FROM recipes WHERE id = ?", (recipe_id,))
            row = cursor.fetchone()
            latest_data = json.loads(row['data'])
            for s in latest_data['steps']:
                if s['index'] == step_index:
                    s['image'] = cos_url
                    break
            cursor.execute(
                "UPDATE recipes SET data = ? WHERE id = ?",
                (json.dumps(latest_data, ensure_ascii=False), recipe_id)
            )
            conn.commit()
            success_count += 1
            business_logger.info(f"  ✓ 步骤 {step_index} 完成并写库: {cos_url}")
        except Exception as e:
            conn.rollback()
            business_logger.error(f"  ✗ 步骤 {step_index} 写库失败: {e}")
        finally:
            cursor.close()
            conn.close()

    return success_count


def main():
    business_logger.info("=" * 60)
    business_logger.info("开始生成菜谱步骤示意图")
    business_logger.info("=" * 60)

    cos_client = get_cos_client()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, data FROM recipes WHERE status = 'published' ORDER BY id")
    recipes = cursor.fetchall()
    cursor.close()
    conn.close()

    business_logger.info(f"共 {len(recipes)} 个菜谱")

    if TEST_MODE:
        business_logger.info("【测试模式】仅处理第一个菜谱的第一个步骤")
        recipes = recipes[:1]

    total_steps = 0
    total_recipes = len(recipes)

    if TEST_MODE:
        for recipe in recipes:
            count = process_recipe(recipe, cos_client)
            total_steps += count
    else:
        # 生产模式：每个菜谱并发处理
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_recipe, recipe, cos_client): recipe for recipe in recipes}

            done = 0
            for future in as_completed(futures):
                total_steps += future.result()
                done += 1
                print(f"\r进度: {done}/{total_recipes}", end="")

    business_logger.info(f"\n\n{'=' * 60}")
    business_logger.info(f"完成！共生成 {total_steps} 张步骤图片")
    business_logger.info("=" * 60)


if __name__ == "__main__":
    main()
