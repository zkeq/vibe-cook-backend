#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from enhance_recipes_with_ai import *

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT * FROM recipes WHERE title='蛋包饭' LIMIT 1")
recipe = cursor.fetchone()

if recipe:
    print("处理蛋包饭...")
    success = process_recipe(recipe)
    print(f"{'✅ 成功' if success else '❌ 失败'}")
    
    # 查看结果
    cursor.execute("SELECT data FROM recipes WHERE id LIKE '%dan-bao-fan%' LIMIT 1")
    result = cursor.fetchone()
    if result:
        import json
        data = json.loads(result["data"])
        print(f"\nID: {data['id']}")
        print(f"食材数: {len(data.get('ingredients', []))}")
        print(f"\n前3个食材:")
        for ing in data.get('ingredients', [])[:3]:
            print(f"  - {ing['name']}: {ing.get('amount', 'N/A')}")
            if ing.get('buying_tip'):
                print(f"    提示: {ing['buying_tip']}")
else:
    print("未找到蛋包饭")

cursor.close()
conn.close()
