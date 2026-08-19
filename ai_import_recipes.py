#!/usr/bin/env python3
# coding: utf-8
"""
使用 AI 直接从 Markdown 生成完整菜谱数据

流程：
1. 读取原始 markdown 文件
2. 直接喂给 AI，让它输出完整的 JSON
3. 保存到数据库

使用方法:
    python3 ai_import_recipes.py --test  # 测试单个
    python3 ai_import_recipes.py         # 处理全部
"""

import os
import sys
import json
import sqlite3
import argparse
import time
from pathlib import Path
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
MAX_WORKERS = 48

# 分类映射
CATEGORY_MAP = {
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

CATEGORY_EN_MAP = {v: k for k, v in CATEGORY_MAP.items()}


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect('data/vibe_cook.db')
    conn.row_factory = sqlite3.Row
    return conn


def generate_english_id(title: str, category: str) -> str:
    """生成英文 ID"""
    pinyin_list = lazy_pinyin(title)
    pinyin_str = "-".join(pinyin_list)
    category_en = CATEGORY_EN_MAP.get(category, "other")
    recipe_id = f"{category_en}_{pinyin_str}".lower()
    recipe_id = recipe_id.replace("(", "").replace(")", "").replace(" ", "-").replace("，", "").replace("、", "-")
    return recipe_id


def call_gemini_api(prompt: str, max_retries: int = 3) -> Optional[str]:
    """调用 Gemini API"""
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
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            business_logger.error(f"API 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None


def markdown_to_recipe(md_content: str, md_path: Path) -> Optional[Dict[str, Any]]:
    """
    使用 AI 将 markdown 转换为完整的菜谱 JSON
    """
    # 从路径推断分类
    category_dir = md_path.parent.name
    category = CATEGORY_MAP.get(category_dir, "其他")

    prompt = f"""
你是一个专业的烹饪数据分析师。请将以下菜谱 Markdown 转换为结构化的 JSON 数据。

**Markdown 内容：**
```markdown
{md_content}
```

**分类**: {category}

请严格按照以下 JSON Schema 输出，**只返回 JSON，不要任何其他文字**：

{{
  "title": "菜谱名称",
  "summary": "菜谱简介（从第一段提取）",
  "difficulty": 1-5的整数（根据"预估烹饪难度"的星数），
  "calories": 整数（从"预估卡路里"提取），
  "duration_min": 整数（预估总时长，分钟），
  "category": "{category}",
  "tags": [],
  "ingredients": [
    {{
      "name": "食材名称",
      "amount": "具体用量(如'2个(约300g)'、'100g'、'20ml')",
      "buying_tip": "购买提示（一句话）",
      "optional": false或true,
      "per_serving": false或true（主料true，调味料false）
    }}
  ],
  "tools": ["炒锅", "菜刀", "砧板"等],
  "servings": {{
    "base": 1,
    "formula": [
      {{"name": "食材名", "expr": "计算公式"}}
    ]
  }},
  "steps": [
    {{
      "index": 1,
      "title": "步骤 1",
      "instruction": "步骤说明",
      "duration_sec": 估算秒数,
      "tips": ["提示1", "提示2"],
      "produces": "产出物名称或null"
    }}
  ],
  "tips": ["全局注意事项1", "全局注意事项2"],
  "cover_image": "",
  "overview_image": ""
}}

**重要规则：**
1. ingredients 必须从"必备原料和工具"部分提取，给出具体用量
2. servings.formula 从"计算"或"每份"部分提取
3. steps 从"操作"部分提取，每步补充 duration_sec 和 tips
4. tips 从"附加内容"部分提取
5. 所有字段必须完整，不能遗漏

只返回 JSON，不要 markdown 代码块标记：
"""

    response = call_gemini_api(prompt)
    if not response:
        return None

    try:
        # 提取 JSON
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            recipe_data = json.loads(response[json_start:json_end])

            # 生成英文 ID
            title = recipe_data.get("title", "未命名")
            recipe_id = generate_english_id(title, category)
            recipe_data["id"] = recipe_id

            return recipe_data
    except Exception as e:
        business_logger.error(f"解析 JSON 失败: {e}")
        business_logger.error(f"响应内容: {response[:500]}")
        return None


def save_recipe(recipe_data: Dict[str, Any]) -> bool:
    """保存菜谱到数据库"""
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
        return True
    except Exception as e:
        business_logger.error(f"保存失败: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def process_markdown_file(md_file: Path, max_retries: int = 5) -> bool:
    """处理单个 markdown 文件，失败会重试"""
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                business_logger.info(f"重试 {attempt}/{max_retries}: {md_file.name}")
                time.sleep(2 ** attempt)  # 指数退避
            else:
                business_logger.info(f"处理: {md_file.name}")

            # 读取 markdown
            with open(md_file, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # AI 转换
            recipe_data = markdown_to_recipe(md_content, md_file)
            if not recipe_data:
                if attempt < max_retries - 1:
                    business_logger.warning(f"  ✗ AI 转换失败，将重试...")
                    continue
                else:
                    business_logger.error(f"  ✗ AI 转换失败，已达最大重试次数")
                    return False

            business_logger.info(f"  ✓ AI 转换完成: {recipe_data['id']}")
            business_logger.info(f"    食材: {len(recipe_data.get('ingredients', []))}, "
                               f"步骤: {len(recipe_data.get('steps', []))}, "
                               f"Tips: {len(recipe_data.get('tips', []))}")

            # 保存
            if save_recipe(recipe_data):
                business_logger.info(f"  ✓ 保存成功")
                return True
            else:
                if attempt < max_retries - 1:
                    business_logger.warning(f"  ✗ 保存失败，将重试...")
                    continue
                else:
                    business_logger.error(f"  ✗ 保存失败，已达最大重试次数")
                    return False

        except Exception as e:
            if attempt < max_retries - 1:
                business_logger.warning(f"处理异常: {e}，将重试...")
                continue
            else:
                business_logger.error(f"处理失败: {e}，已达最大重试次数")
                return False

    return False


def main():
    parser = argparse.ArgumentParser(description="使用 AI 直接从 Markdown 导入菜谱")
    parser.add_argument("--test", action="store_true", help="仅测试一个")
    parser.add_argument("--dishes-dir", default="../001-HowToCook-master/dishes",
                       help="HowToCook dishes 目录")
    args = parser.parse_args()

    dishes_path = Path(args.dishes_dir)
    if not dishes_path.exists():
        print(f"❌ 目录不存在: {args.dishes_dir}")
        return

    # 收集所有 markdown 文件
    md_files = []
    for category_dir in dishes_path.iterdir():
        if not category_dir.is_dir() or category_dir.name == "template":
            continue
        md_files.extend(list(category_dir.rglob("*.md")))

    if args.test:
        print("=" * 60)
        print("测试模式")
        print("=" * 60)
        if md_files:
            success = process_markdown_file(md_files[0])
            print(f"\n{'✅ 成功' if success else '❌ 失败'}")
        else:
            print("❌ 没有找到文件")
    else:
        total = len(md_files)
        print("=" * 60)
        print(f"开始处理 {total} 个菜谱，{MAX_WORKERS} 线程")
        print("=" * 60)

        success_count = 0
        failed_files = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_markdown_file, f): f for f in md_files}

            for future in as_completed(futures):
                md_file = futures[future]
                if future.result():
                    success_count += 1
                else:
                    failed_files.append(md_file)

                processed = success_count + len(failed_files)
                print(f"\r进度: {processed}/{total} "
                      f"(✅{success_count} ❌{len(failed_files)})", end="")

        # 如果有失败的，单独重试
        if failed_files:
            print(f"\n\n{'=' * 60}")
            print(f"发现 {len(failed_files)} 个失败，开始重试...")
            print("=" * 60)

            retry_count = 0
            for md_file in failed_files:
                print(f"\n重新处理: {md_file.name}")
                if process_markdown_file(md_file, max_retries=10):
                    success_count += 1
                    retry_count += 1
                    print(f"  ✅ 重试成功 ({retry_count}/{len(failed_files)})")
                else:
                    print(f"  ❌ 重试仍然失败")

        print(f"\n\n{'=' * 60}")
        print(f"全部完成！")
        print(f"✅ 成功: {success_count}")
        print(f"❌ 失败: {total - success_count}")
        print(f"📊 成功率: {success_count/total*100:.1f}%")
        print("=" * 60)


if __name__ == "__main__":
    main()
