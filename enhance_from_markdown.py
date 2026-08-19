#!/usr/bin/env python3
# coding: utf-8
"""
从原始 Markdown 重新解析并用 AI 增强

流程：
1. 读取原始 HowToCook markdown 文件
2. 完整解析所有信息（食材、步骤、tips等）
3. 用 AI 增强缺失字段
4. 保存到数据库
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional

# 导入现有的解析和增强函数
from import_howtocook import parse_markdown_recipe
from enhance_recipes_with_ai import (
    enhance_recipe_with_ai,
    save_enhanced_recipe,
    business_logger,
    MAX_WORKERS
)


def process_markdown_file(md_file: Path) -> bool:
    """
    处理单个 markdown 文件
    
    Returns:
        成功返回 True，失败返回 False
    """
    try:
        business_logger.info(f"处理文件: {md_file.name}")
        
        # 1. 从原始 markdown 解析
        recipe_data = parse_markdown_recipe(str(md_file))
        if not recipe_data:
            business_logger.error(f"  ✗ 解析失败")
            return False
        
        business_logger.info(f"  ✓ 原始数据解析完成")
        business_logger.info(f"    - 食材: {len(recipe_data.get('ingredients', []))} 个")
        business_logger.info(f"    - 步骤: {len(recipe_data.get('steps', []))} 个")
        business_logger.info(f"    - Tips: {len(recipe_data.get('tips', []))} 条")
        
        # 2. AI 增强
        enhanced_data = enhance_recipe_with_ai(recipe_data)
        
        # 3. 保存到数据库
        save_enhanced_recipe(enhanced_data)
        
        return True
    except Exception as e:
        business_logger.error(f"处理失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="从原始 Markdown 重新解析并用 AI 增强")
    parser.add_argument("--test", action="store_true", help="仅测试处理一个菜谱")
    parser.add_argument("--dishes-dir", default="../001-HowToCook-master/dishes", 
                       help="HowToCook dishes 目录路径")
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
        # 递归查找所有 .md 文件
        md_files.extend(list(category_dir.rglob("*.md")))

    if args.test:
        # 测试模式：只处理一个
        print("=" * 60)
        print("测试模式：处理一个菜谱")
        print("=" * 60)
        if md_files:
            success = process_markdown_file(md_files[0])
            print(f"\n{'✅ 测试成功' if success else '❌ 测试失败'}")
        else:
            print("❌ 没有找到 markdown 文件")
    else:
        # 处理全部
        total = len(md_files)
        print("=" * 60)
        print(f"开始处理 {total} 个菜谱，使用 {MAX_WORKERS} 个线程")
        print("=" * 60)

        success_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_markdown_file, md_file): md_file for md_file in md_files}

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


if __name__ == "__main__":
    main()
