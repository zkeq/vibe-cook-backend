#!/usr/bin/env python3
import json, sqlite3
from pathlib import Path
from pypinyin import lazy_pinyin

DB_PATH = "data/vibe_cook.db"
HOWTOCOOK_DIR = Path("../HowToCook-official/dishes")

def find_markdown_file(recipe_id, recipe_title):
    categories = ["vegetable_dish", "meat_dish", "aquatic", "breakfast", "staple", "semi-finished", "soup", "drink", "dessert", "condiment"]
    for category in categories:
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

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT id, data FROM recipes WHERE status = 'published' ORDER BY id")
recipes = cursor.fetchall()
cursor.close()
conn.close()

total, found, not_found = len(recipes), 0, []
for recipe in recipes:
    recipe_id = recipe['id']
    recipe_data = json.loads(recipe['data'])
    title = recipe_data.get('title', '')
    if find_markdown_file(recipe_id, title):
        found += 1
    else:
        not_found.append((recipe_id, title))

print("=" * 60)
print(f"总计: {total}")
print(f"✅ 找到 markdown: {found}")
print(f"❌ 未找到: {len(not_found)}")
print(f"📊 匹配率: {found/total*100:.1f}%")
if not_found:
    print(f"\n未找到的菜谱 (前10个):")
    for rid, title in not_found[:10]:
        print(f"  - {title} ({rid})")
print("=" * 60)
