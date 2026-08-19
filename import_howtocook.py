#!/usr/bin/env python3
# coding: utf-8
"""
HowToCook 数据导入脚本

从 HowToCook 项目的 Markdown 文件解析菜谱数据并导入到数据库

使用方法:
    python import_howtocook.py /path/to/HowToCook/dishes
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from business import create_recipe
from logger import business_logger

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
    "condiment": "酱料",
}


def parse_markdown_recipe(md_path: str) -> Optional[Dict[str, Any]]:
    """
    解析单个 Markdown 菜谱文件

    Args:
        md_path: Markdown 文件路径

    Returns:
        符合前端 Recipe 类型的字典，或 None（如果解析失败）
    """
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取标题
        title_match = re.search(r'^# (.+?)的做法', content, re.MULTILINE)
        if not title_match:
            return None
        title = title_match.group(1).strip()

        # 提取简介（第一段文字）
        summary_match = re.search(r'^# .+?\n\n(.+?)\n\n', content, re.MULTILINE | re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        # 提取难度
        difficulty_match = re.search(r'预估烹饪难度：([★☆]+)', content)
        difficulty = len(difficulty_match.group(1).replace('☆', '')) if difficulty_match else 1

        # 提取卡路里
        calories_match = re.search(r'预估卡路里：(\d+)', content)
        calories = int(calories_match.group(1)) if calories_match else 0

        # 提取食材
        ingredients = []
        ingredients_section = re.search(r'## 必备原料和工具\n\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
        if ingredients_section:
            for line in ingredients_section.group(1).split('\n'):
                line = line.strip()
                if line and line.startswith('*'):
                    name = line.lstrip('* ').strip()
                    ingredients.append({
                        "name": name,
                        "amount": "适量",
                        "per_serving": False
                    })

        # 提取计算公式（份数）
        servings_base = 1
        servings_formula = []
        calc_section = re.search(r'## 计算\n\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
        if calc_section:
            calc_text = calc_section.group(1)
            # 提取份数
            servings_match = re.search(r'一份正好够 (\d+) 个人食用', calc_text)
            if servings_match:
                servings_base = int(servings_match.group(1))

            # 提取配料公式
            for line in calc_text.split('\n'):
                if '*' in line and '份数' in line:
                    parts = line.split('*')
                    if len(parts) >= 2:
                        name = parts[0].strip().lstrip('* ')
                        expr = parts[1].strip()
                        servings_formula.append({
                            "name": name,
                            "expr": expr
                        })

        # 提取步骤
        steps = []
        steps_section = re.search(r'## 操作\n\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
        if steps_section:
            step_lines = steps_section.group(1).strip().split('\n')
            for i, line in enumerate(step_lines, 1):
                line = line.strip()
                if line and re.match(r'^\d+\.', line):
                    instruction = re.sub(r'^\d+\.\s*', '', line)
                    steps.append({
                        "index": i,
                        "title": f"步骤 {i}",
                        "instruction": instruction,
                    })

        # 提取提示
        tips = []
        tips_section = re.search(r'## 附加内容\n\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
        if tips_section:
            for line in tips_section.group(1).split('\n'):
                line = line.strip()
                if line and line.startswith('*'):
                    tip = line.lstrip('* ').strip()
                    tips.append(tip)

        # 估算烹饪时间（基于步骤数量）
        duration_min = max(10, len(steps) * 5)

        # 获取分类
        category_dir = Path(md_path).parent.name
        category = CATEGORY_MAP.get(category_dir, "其他")

        # 生成 ID（拼音或英文）
        recipe_id = Path(md_path).stem.lower().replace(' ', '-')

        # 构建完整的菜谱数据
        recipe_data = {
            "id": recipe_id,
            "title": title,
            "summary": summary,
            "difficulty": difficulty,
            "calories": calories,
            "duration_min": duration_min,
            "category": category,
            "cover_image": "",
            "tags": [],
            "ingredients": ingredients,
            "tools": [],
            "servings": {
                "base": servings_base,
                "formula": servings_formula
            },
            "steps": steps,
            "tips": tips,
            "overview_image": ""
        }

        return recipe_data

    except Exception as e:
        business_logger.error(f"解析失败: {md_path}, error={e}")
        return None


def import_from_directory(dishes_dir: str) -> Dict[str, int]:
    """
    从 HowToCook dishes 目录导入所有菜谱

    Args:
        dishes_dir: HowToCook 的 dishes 目录路径

    Returns:
        导入统计 {"success": 成功数, "failed": 失败数}
    """
    stats = {"success": 0, "failed": 0}
    dishes_path = Path(dishes_dir)

    if not dishes_path.exists():
        print(f"错误: 目录不存在 {dishes_dir}")
        return stats

    # 遍历所有分类目录
    for category_dir in dishes_path.iterdir():
        if not category_dir.is_dir():
            continue
        if category_dir.name == "template":
            continue

        print(f"\n处理分类: {category_dir.name}")

        # 遍历该分类下的所有 .md 文件
        md_files = list(category_dir.rglob("*.md"))
        for md_file in md_files:
            try:
                print(f"  解析: {md_file.relative_to(category_dir)}")
                recipe_data = parse_markdown_recipe(str(md_file))

                if recipe_data:
                    create_recipe(recipe_data)
                    print(f"    ✓ 导入成功: {recipe_data['title']}")
                    stats["success"] += 1
                else:
                    print(f"    ✗ 解析失败")
                    stats["failed"] += 1

            except Exception as e:
                print(f"    ✗ 导入失败: {e}")
                stats["failed"] += 1

    return stats


def main():
    if len(sys.argv) < 2:
        print("使用方法: python import_howtocook.py /path/to/HowToCook/dishes")
        print("示例: python import_howtocook.py ../001-HowToCook-master/dishes")
        sys.exit(1)

    dishes_dir = sys.argv[1]
    print(f"开始导入 HowToCook 数据...")
    print(f"源目录: {dishes_dir}\n")

    stats = import_from_directory(dishes_dir)

    print(f"\n导入完成!")
    print(f"成功: {stats['success']}")
    print(f"失败: {stats['failed']}")
    print(f"总计: {stats['success'] + stats['failed']}")


if __name__ == "__main__":
    main()
