#!/usr/bin/env python3
# coding: utf-8
"""
一次性脚本：把每个菜谱对应的 markdown 文件路径写入数据库 markdown_path 字段
之后所有脚本直接 SELECT markdown_path 即可，不用再跑匹配逻辑
"""

import sqlite3
from pathlib import Path
from pypinyin import lazy_pinyin
from logger import business_logger

DB_PATH = "data/vibe_cook.db"
HOWTOCOOK_ROOT = Path("/Users/zkeq/Desktop/Code/vibe-cook_workspace/001-HowToCook-master")
HOWTOCOOK_DIR = HOWTOCOOK_ROOT / "dishes"

CATEGORIES = [
    "vegetable_dish", "meat_dish", "aquatic", "breakfast", "staple",
    "semi-finished", "soup", "drink", "dessert", "condiment"
]


def find_markdown_file(recipe_id: str) -> Path | None:
    for category in CATEGORIES:
        category_path = HOWTOCOOK_DIR / category
        if not category_path.exists():
            continue

        for item in category_path.iterdir():
            if item.is_file() and item.suffix == '.md':
                file_pinyin = '-'.join(lazy_pinyin(item.stem)).lower()
                if file_pinyin in recipe_id:
                    return item
            elif item.is_dir():
                dir_pinyin = '-'.join(lazy_pinyin(item.name)).lower()
                if dir_pinyin in recipe_id:
                    md_files = list(item.glob("*.md"))
                    if md_files:
                        return md_files[0]
                for md_file in item.glob("*.md"):
                    file_pinyin = '-'.join(lazy_pinyin(md_file.stem)).lower()
                    if file_pinyin in recipe_id:
                        return md_file

    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 加字段（已存在则忽略）
    try:
        cursor.execute("ALTER TABLE recipes ADD COLUMN markdown_path TEXT")
        conn.commit()
        business_logger.info("已添加 markdown_path 字段")
    except Exception:
        business_logger.info("markdown_path 字段已存在，跳过")

    cursor.execute("SELECT id, title FROM recipes WHERE status = 'published' ORDER BY id")
    recipes = cursor.fetchall()

    matched = 0
    unmatched = []

    for row in recipes:
        recipe_id = row['id']
        md_file = find_markdown_file(recipe_id)
        if md_file:
            # 存相对于 HowToCook 仓库根目录的路径，如 dishes/aquatic/咖喱炒蟹.md
            relative_path = md_file.relative_to(HOWTOCOOK_ROOT)
            cursor.execute(
                "UPDATE recipes SET markdown_path = ? WHERE id = ?",
                (str(relative_path), recipe_id)
            )
            matched += 1
        else:
            unmatched.append((recipe_id, row['title']))

    conn.commit()
    cursor.close()
    conn.close()

    business_logger.info(f"\n完成：{matched}/{len(recipes)} 匹配成功")
    if unmatched:
        business_logger.info(f"未匹配 {len(unmatched)} 个：")
        for rid, title in unmatched:
            business_logger.info(f"  - {rid} ({title})")
    else:
        business_logger.info("100% 匹配！")


if __name__ == "__main__":
    main()
