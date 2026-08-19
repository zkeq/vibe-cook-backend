#!/usr/bin/env python3
# coding: utf-8
"""
使用 AI 增强菜谱数据脚本

功能：
1. 读取现有菜谱数据
2. 使用 Gemini API 补全缺失字段：
   - 每个食材的 buying_tip（购买提示）
   - 每个步骤的 duration_sec（时长）和 tips（提示）
   - 规范化的 amount（用量）
   - 所需工具 tools
   - 生成英文 ID
3. 18 线程并发处理
4. 保存到新表 recipes_enhanced

使用方法:
    python3 enhance_recipes_with_ai.py --test  # 测试单个菜谱
    python3 enhance_recipes_with_ai.py         # 处理全部菜谱
"""

import os
import sys
import json
import sqlite3
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional
import requests
from pypinyin import lazy_pinyin
from logger import business_logger
from pipeline_env import (
    CHAT_API_URL as API_URL,
    CHATFIRE_CHAT_MODEL as MODEL,
    require_chatfire_key,
)
MAX_WORKERS = 18

# 分类映射（中文 -> 英文）
CATEGORY_EN_MAP = {
    "素菜": "vegetable",
    "荤菜": "meat",
    "水产": "seafood",
    "早餐": "breakfast",
    "主食": "staple",
    "半成品加工": "semi-finished",
    "汤": "soup",
    "饮料": "drink",
    "甜品": "dessert",
    "酱料": "condiment",
    "其他": "other"
}


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect('data/vibe_cook.db')
    conn.row_factory = sqlite3.Row
    return conn


def generate_english_id(title: str, category: str) -> str:
    """
    生成英文 ID

    使用规则：category_pinyin-of-title
    如：vegetable_xi-hong-shi-chao-ji-dan
    """
    # 获取拼音
    pinyin_list = lazy_pinyin(title)
    pinyin_str = "-".join(pinyin_list)
    # 获取分类英文
    category_en = CATEGORY_EN_MAP.get(category, "other")
    # 组合
    recipe_id = f"{category_en}_{pinyin_str}".lower()
    # 清理特殊字符
    recipe_id = recipe_id.replace("(", "").replace(")", "").replace(" ", "-")
    return recipe_id


def call_gemini_api(prompt: str, max_retries: int = 3) -> Optional[str]:
    """
    调用 Gemini API

    Args:
        prompt: 提示词
        max_retries: 最大重试次数

    Returns:
        API 响应内容，失败返回 None
    """
    headers = {
        "Authorization": f"Bearer {require_chatfire_key()}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            business_logger.error(f"API 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
            else:
                return None


def enhance_recipe_with_ai(recipe_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用 AI 增强单个菜谱数据

    补全：
    1. 每个 ingredient 的 buying_tip
    2. 每个 ingredient 的规范化 amount
    3. 每个 step 的 duration_sec 和 tips
    4. tools 列表
    5. 生成英文 ID
    """
    title = recipe_data["title"]
    category = recipe_data.get("category", "其他")

    business_logger.info(f"开始增强菜谱: {title}")

    # 1. 生成英文 ID
    new_id = generate_english_id(title, category)
    recipe_data["id"] = new_id

    # 2. 增强食材信息
    ingredients = recipe_data.get("ingredients", [])
    steps = recipe_data.get("steps", [])

    # 如果食材列表为空，从步骤中提取
    if not ingredients:
        business_logger.info(f"  ! 食材列表为空，从步骤中提取...")
        steps_text = "\n".join([f"步骤{s['index']}: {s['instruction']}" for s in steps])

        prompt = f"""
你是一个专业的烹饪助手。请从以下菜谱《{title}》的步骤中提取出所有需要的食材。

步骤内容：
{steps_text}

请列出所有食材，并为每个食材补充详细信息：
1. name: 食材名称
2. amount: 具体用量（如"1个洋葱(约150g)"、"2个鸡蛋"、"100g米饭"、"20ml番茄酱"）
3. buying_tip: 购买时的注意事项（一句话）
4. optional: 是否可选（true/false）
5. per_serving: 是否随份数缩放（主料为true，调味料为false）

只返回 JSON 数组，不要其他解释：
[
  {{"name": "洋葱", "amount": "1个(约150g)", "buying_tip": "选择表皮干燥、无发芽的", "optional": false, "per_serving": true}},
  ...
]
"""
        response = call_gemini_api(prompt)
        if response:
            try:
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    extracted_ingredients = json.loads(response[json_start:json_end])
                    recipe_data["ingredients"] = extracted_ingredients
                    business_logger.info(f"  ✓ 已从步骤中提取 {len(extracted_ingredients)} 个食材")
                    ingredients = extracted_ingredients
            except Exception as e:
                business_logger.error(f"  ✗ 提取食材失败: {e}")

    # 如果有食材但信息不完整，增强它们
    elif ingredients:
        prompt = f"""
你是一个专业的烹饪助手。请为以下菜谱《{title}》的食材补全信息。

当前食材列表：
{json.dumps(ingredients, ensure_ascii=False, indent=2)}

请为每个食材补充完整信息：
1. amount: 规范化的用量（如"2个(约300g)"、"100g"、"1勺"），如果原本是"适量"则根据常识给出具体用量
2. buying_tip: 购买时的注意事项（一句话，如"选择色泽鲜艳、无斑点的"）
3. optional: 是否可选（true/false）
4. per_serving: 是否随份数缩放（true/false，基础食材如主料为true，调味料为false）

只返回 JSON 数组，不要其他解释：
[
  {{"name": "...", "amount": "...", "buying_tip": "...", "optional": false, "per_serving": true}},
  ...
]
"""
        response = call_gemini_api(prompt)
        if response:
            try:
                # 提取 JSON
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    enhanced_ingredients = json.loads(response[json_start:json_end])
                    recipe_data["ingredients"] = enhanced_ingredients
                    business_logger.info(f"  ✓ 食材信息已增强")
            except Exception as e:
                business_logger.error(f"  ✗ 解析食材 JSON 失败: {e}")

    # 3. 增强步骤信息
    steps = recipe_data.get("steps", [])
    if steps:
        prompt = f"""
你是一个专业的烹饪助手。请为以下菜谱《{title}》的步骤补全信息。

当前步骤列表：
{json.dumps(steps, ensure_ascii=False, indent=2)}

请为每个步骤补充：
1. duration_sec: 该步骤需要的时间（秒），如果是"洗净"/"切"等准备工作给30-60秒，炒菜给120-300秒，等待/煮/炖根据常识给出
2. tips: 该步骤的注意事项（数组，1-2条提示，如["火候要适中","避免翻炒过度"]），如果没有特别注意事项可以为空数组
3. produces: 该步骤产生的中间产物名称（如"鸡蛋液"、"半熟鸡蛋"），没有则为 null

只返回 JSON 数组，不要其他解释：
[
  {{"index": 1, "title": "...", "instruction": "...", "duration_sec": 60, "tips": ["..."], "produces": null}},
  ...
]
"""
        response = call_gemini_api(prompt)
        if response:
            try:
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    enhanced_steps = json.loads(response[json_start:json_end])
                    recipe_data["steps"] = enhanced_steps
                    business_logger.info(f"  ✓ 步骤信息已增强")
            except Exception as e:
                business_logger.error(f"  ✗ 解析步骤 JSON 失败: {e}")

    # 4. 补充工具列表
    if not recipe_data.get("tools"):
        prompt = f"""
根据菜谱《{title}》的以下信息，列出需要的厨房工具。

食材：{json.dumps(ingredients, ensure_ascii=False)}
步骤：{json.dumps(steps, ensure_ascii=False)}

只返回工具名称的 JSON 数组（如炒锅、菜刀、砧板、碗、筷子等），不要其他解释：
["工具1", "工具2", ...]
"""
        response = call_gemini_api(prompt)
        if response:
            try:
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    tools = json.loads(response[json_start:json_end])
                    recipe_data["tools"] = tools
                    business_logger.info(f"  ✓ 工具列表已补充: {tools}")
            except Exception as e:
                business_logger.error(f"  ✗ 解析工具 JSON 失败: {e}")

    # 5. 补充全局注意事项 tips
    if not recipe_data.get("tips"):
        prompt = f"""
根据菜谱《{title}》，提供 3-5 条全局烹饪注意事项或小技巧。

食材：{json.dumps(ingredients, ensure_ascii=False)}
步骤：{json.dumps(steps, ensure_ascii=False)}

这些 tips 应该是：
- 整道菜的关键技巧（如"全程保持中火"）
- 食材选择建议（如"选用隔夜米饭口感更好"）
- 口味调整建议（如"喜欢甜味可多加糖"）
- 常见失败原因（如"避免翻炒过度导致变色"）

只返回字符串数组，不要其他解释：
["技巧1", "技巧2", ...]
"""
        response = call_gemini_api(prompt)
        if response:
            try:
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    tips = json.loads(response[json_start:json_end])
                    recipe_data["tips"] = tips
                    business_logger.info(f"  ✓ 全局注意事项已补充: {len(tips)} 条")
            except Exception as e:
                business_logger.error(f"  ✗ 解析 tips JSON 失败: {e}")
    else:
        business_logger.info(f"  ✓ 保留原有注意事项: {len(recipe_data.get('tips', []))} 条")

    business_logger.info(f"✅ 菜谱增强完成: {title} -> {new_id}")
    return recipe_data


def save_enhanced_recipe(recipe_data: Dict[str, Any]):
    """保存增强后的菜谱到数据库"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        recipe_id = recipe_data["id"]
        title = recipe_data["title"]
        category = recipe_data.get("category", "")
        cover_image = recipe_data.get("cover_image", "")
        data_json = json.dumps(recipe_data, ensure_ascii=False)

        sql = """
            INSERT OR REPLACE INTO recipes (id, title, category, cover_image, data, status)
            VALUES (?, ?, ?, ?, ?, 'published')
        """
        cursor.execute(sql, (recipe_id, title, category, cover_image, data_json))
        conn.commit()
        business_logger.info(f"  ✓ 已保存到数据库: {recipe_id}")
    except Exception as e:
        business_logger.error(f"  ✗ 保存失败: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def process_recipe(recipe_row) -> bool:
    """
    处理单个菜谱

    Returns:
        成功返回 True，失败返回 False
    """
    try:
        recipe_data = json.loads(recipe_row["data"])
        enhanced_data = enhance_recipe_with_ai(recipe_data)
        save_enhanced_recipe(enhanced_data)
        return True
    except Exception as e:
        business_logger.error(f"处理菜谱失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="使用 AI 增强菜谱数据")
    parser.add_argument("--test", action="store_true", help="仅测试处理一个菜谱")
    args = parser.parse_args()

    conn = get_db_connection()
    cursor = conn.cursor()

    if args.test:
        # 测试模式：只处理一个
        print("=" * 60)
        print("测试模式：处理一个菜谱")
        print("=" * 60)
        cursor.execute("SELECT * FROM recipes WHERE status='published' LIMIT 1")
        recipe = cursor.fetchone()
        if recipe:
            success = process_recipe(recipe)
            print(f"\n{'✅ 测试成功' if success else '❌ 测试失败'}")
        else:
            print("❌ 没有找到菜谱")
    else:
        # 处理全部
        cursor.execute("SELECT COUNT(*) as total FROM recipes WHERE status='published'")
        total = cursor.fetchone()["total"]

        print("=" * 60)
        print(f"开始处理 {total} 个菜谱，使用 {MAX_WORKERS} 个线程")
        print("=" * 60)

        cursor.execute("SELECT * FROM recipes WHERE status='published'")
        recipes = cursor.fetchall()

        success_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_recipe, recipe): recipe for recipe in recipes}

            for future in as_completed(futures):
                if future.result():
                    success_count += 1
                else:
                    failed_count += 1

                print(f"\r进度: {success_count + failed_count}/{total} "
                      f"(成功: {success_count}, 失败: {failed_count})", end="")

        print(f"\n\n{'=' * 60}")
        print(f"处理完成！")
        print(f"成功: {success_count}")
        print(f"失败: {failed_count}")
        print(f"总计: {total}")
        print("=" * 60)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
