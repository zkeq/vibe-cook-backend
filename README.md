# Vibe Cook 开放数据

菜谱结构化数据和配图，协议与上游 [HowToCook](https://github.com/Anduin2017/HowToCook) 相同：**[The Unlicense](./LICENSE)**（公共领域）。

Vibe Cook **应用程序代码**仍是 [Business Source License 1.1](https://github.com/zkeq/vibe-cook-backend/blob/main/LICENSE)，不在本数据授权范围内。

## 内容

| 路径 | 说明 |
| --- | --- |
| `json/recipes.json` | 全部结构化菜谱（一份 JSON） |
| `json/index.json` | 菜谱摘要索引（含 `markdown_path` 对 HowToCook 原仓库、`json_path` 对本数据集） |
| `json/recipes/<id>.json` | 单份菜谱结构化数据 |
| `vibe_cook.db` | 同上数据的 SQLite |
| `images/ai-generated/` | 封面原图 |
| `images/overview/` | 全解图原图 |
| `images/steps/` | 步骤图原图 |
| `manifest.tsv` | 相对路径与文件大小 |

图片为原图，未重新压缩。体积较大，使用 **Git LFS** 存储。

## 获取

```bash
git clone --branch dataset --single-branch https://github.com/zkeq/vibe-cook-backend.git vibe-cook-dataset
cd vibe-cook-dataset
git lfs pull
```

只跑后端请克隆 `main`，不要 `git lfs pull` 原图。

## 图片路径

JSON / SQLite 里只存相对路径，不含任何 CDN 前缀，自行拼接：

| 用法 | 拼法 |
| --- | --- |
| 本地文件 | `images/` + 相对路径 |
| 自建 CDN | `https://your-cdn.example/` + 相对路径 |

例如 `cover_image` 为 `ai-generated/other_chao-hua-dan.jpg`：

- 本地：`images/ai-generated/other_chao-hua-dan.jpg`
- 远程：`https://your-cdn.example/ai-generated/other_chao-hua-dan.jpg`
