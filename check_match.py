#!/usr/bin/env python3
# coding: utf-8
"""检查能匹配到多少菜谱"""

import sys
import json
import sqlite3
from pathlib import Path
from pypinyin import lazy_pinyin

HOWTOCOOK_DIR = Path("../HowToCook-official/dishes")
DB_PATH = "data/vibe_cook.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def match_recipe_in_db(cursor, recipe_dir_name: str, category: str):
    """在数据库中查找匹配的菜谱"""
    # 方式1：精确匹配 title
    cursor.execute("""
        SELECT id, data FROM recipes
        WHERE json_extract(data, '$.title') = ?
    """, (recipe_dir_name,))
    result = cursor.fetchone()
    if result:
        return result, "精确匹配"

    # 方式2：模糊匹配
    cursor.execute("""
        SELECT id, data FROM recipes
        WHERE json_extract(data, '$.title') LIKE ?
    """, (f'%{recipe_dir_name}%',))
    result = cursor.fetchone()
    if result:
        return result, "模糊匹配"

    # 方式3：通过ID匹配
    pinyin_str = "-".join(lazy_pinyin(recipe_dir_name)).lower()
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
            return result, "ID匹配"

    return None, None

def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 统计
    total_dirs = 0
    matched = 0
    unmatched = []
    match_types = {"精确匹配": 0, "模糊匹配": 0, "ID匹配": 0}

    for category_dir in HOWTOCOOK_DIR.iterdir():
        if not category_dir.is_dir() or category_dir.name == "template":
            continue

        for recipe_dir in category_dir.iterdir():
            if not recipe_dir.is_dir():
                continue

            # 检查是否有图片
            has_images = any(
                f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
                for f in recipe_dir.iterdir()
            )

            if not has_images:
                continue

            total_dirs += 1
            recipe_dir_name = recipe_dir.name
            category = category_dir.name

            result, match_type = match_recipe_in_db(cursor, recipe_dir_name, category)

            if result:
                matched += 1
                match_types[match_type] += 1
                recipe_data = json.loads(result["data"])
                print(f"✓ {recipe_dir_name} -> {recipe_data.get('title')} ({match_type})")
            else:
                unmatched.append(f"{category}/{recipe_dir_name}")
                print(f"✗ {recipe_dir_name} (未匹配)")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print(f"总计有图片的菜谱目录: {total_dirs}")
    print(f"✅ 匹配成功: {matched}")
    print(f"   - 精确匹配: {match_types['精确匹配']}")
    print(f"   - 模糊匹配: {match_types['模糊匹配']}")
    print(f"   - ID匹配: {match_types['ID匹配']}")
    print(f"❌ 未匹配: {len(unmatched)}")
    print(f"📊 匹配率: {matched/total_dirs*100:.1f}%")

    if unmatched:
        print(f"\n未匹配的菜谱目录:")
        for u in unmatched[:20]:
            print(f"  - {u}")
        if len(unmatched) > 20:
            print(f"  ... 还有 {len(unmatched) - 20} 个")
    print("=" * 60)

if __name__ == "__main__":
    main()
