# Vibe Cook 开放数据

菜谱结构化数据和配图，协议与上游 [HowToCook](https://github.com/Anduin2017/HowToCook) 相同：**[The Unlicense](./LICENSE)**（公共领域）。

Vibe Cook **应用程序代码**仍是 [Business Source License 1.1](https://github.com/zkeq/vibe-cook-backend/blob/main/LICENSE)，不在本数据授权范围内。

## 内容

| 路径 | 说明 |
| --- | --- |
| `json/recipes.json` | 全部结构化菜谱（一份 JSON） |
| `json/index.json` | 菜谱摘要索引 |
| `json/recipes/<id>.json` | 单份菜谱结构化数据 |
| `vibe_cook.db` | 同上数据的 SQLite |
| `images/ai-generated/` | 封面原图 |
| `images/overview/` | 全解图原图 |
| `images/steps/` | 步骤图原图 |
| `manifest.tsv` | COS URL 与本地相对路径对照 |

图片均为 COS 原图，未重新压缩。体积较大，使用 **Git LFS** 存储。

## 获取

```bash
git clone --branch dataset --single-branch https://github.com/zkeq/vibe-cook-backend.git vibe-cook-dataset
cd vibe-cook-dataset
git lfs pull
```

默认 `main` 分支不含原图，避免普通克隆下载数 GB。只想要数据时请拉 `dataset` 分支。

## 本地对照

线上地址 `https://cos.onmicrosoft.cn/cook/<相对路径>` 对应本目录 `images/<相对路径>`。

例如：

`https://cos.onmicrosoft.cn/cook/ai-generated/other_chao-hua-dan.jpg`  
→ `images/ai-generated/other_chao-hua-dan.jpg`
