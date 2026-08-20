# 🥘 Vibe Cook Backend

Vibe Cook 的后端：把 [HowToCook](https://github.com/Anduin2017/HowToCook) 的 Markdown 菜谱变成结构化 JSON，再交给前端做沉浸式分步烹饪。

<p>
  <a href="https://cook-api.corerevive.cn/docs"><img src="https://img.shields.io/badge/📚_API_文档-cook--api.corerevive.cn-0ea5e9?style=for-the-badge" alt="API Docs"></a>
  &nbsp;
  <a href="https://github.com/zkeq/vibe-cook"><img src="https://img.shields.io/badge/🍳_前端-vibe--cook-ff6b35?style=for-the-badge" alt="Frontend"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/License-BUSL--1.1-red?style=for-the-badge" alt="BUSL-1.1">
</p>

前端仓库：[zkeq/vibe-cook](https://github.com/zkeq/vibe-cook) · 在线 App：<https://cook.corerevive.cn>

---

## ✨ 特点

- 🪶 **极简** — 扁平结构，路由 → 鉴权 → 业务 → SQL
- 💾 **SQLite 单文件** — 零外部依赖，首次启动自动建表
- 🔐 **JWT** — 管理员 / 编辑才能写菜谱
- 🍳 **为跟做而生** — 列表、搜索、随机、分类、完整分步 JSON

## 🚀 快速开始

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
python main.py
```

| | |
| --- | --- |
| 📚 API 文档 | <http://localhost:8000/docs> |
| ❤️ 健康检查 | <http://localhost:8000/health> |
| 👤 默认管理员 | `admin` / `admin123`（请立刻改密） |

前端把 `NEXT_PUBLIC_API_URL` 指到 `http://localhost:8000/api/v1` 即可联调。

## ⚙️ 配置

| 文件 | 用途 |
| --- | --- |
| `config.example.yaml` | 服务端模板（host / SQLite / JWT） |
| `config.yaml` | 本地配置，**不要提交** |
| `.env.example` | 灌库 / 生图脚本的密钥模板 |
| `.env` | 脚本密钥，**不要提交** |

`python main.py` 只读 `config.yaml`。AI 灌库、生图、上传 COS 等脚本读 `.env`。

```bash
cp .env.example .env
# 填 CHATFIRE_API_KEY、COS_SECRET_ID、COS_SECRET_KEY
```

## 📡 API

全部带 `/api/v1` 前缀。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/recipes` | 菜谱列表（分页、分类） |
| `GET` | `/api/v1/recipes/{id}` | 菜谱详情 |
| `GET` | `/api/v1/recipes/search` | 搜索 |
| `GET` | `/api/v1/recipes/random` | 随机菜谱 |
| `GET` | `/api/v1/recipes/categories` | 分类 |
| `POST` | `/api/v1/recipes` | 写入 / 更新（需 editor） |
| `POST` | `/api/v1/auth/login-by-password` | 密码登录 |

完整字段契约见前端仓库 [`API_SPEC.md`](https://github.com/zkeq/vibe-cook/blob/main/API_SPEC.md)。

## 📥 菜谱数据

仓库自带 `data/vibe_cook.db`（从 HowToCook 结构化后的 SQLite）。`python main.py` 后即可直接出菜。

若要重新从 HowToCook Markdown 灌库：

```bash
# 仓库旁准备 HowToCook 源，默认读 ../HowToCook-official/dishes
python import_howtocook.py
```

可选的 AI 增强 / 生图（需要 `.env` 密钥）：

```bash
python ai_import_recipes.py --test
python enhance_recipes_with_ai.py --test
python generate_recipe_images.py
python generate_step_images.py --test
python generate_overview_guide.py
python upload_images_to_cos.py
```

## 🐳 Docker

```bash
cp config.example.yaml config.yaml
./docker-start.sh start
```

数据文件在 `./data/vibe_cook.db`。

## 📁 目录

```
main.py              # 入口、CORS、启动建表
router.py            # 路由与参数校验
auth.py              # JWT / 密码
db.py                # SQLite
business/            # 业务（recipe / user）
sql/init.sql         # 建表
pipeline_env.py      # 脚本密钥（只读环境变量）
import_howtocook.py  # Markdown → SQLite
```

## 🛡️ 生产环境清单

1. `JWT.secret_key` 换成足够长的随机串
2. `SERVER.debug: false`，CORS 只放行前端域名
3. 改掉默认管理员密码
4. 不要提交 `config.yaml`、`.env`、`*.db`

## 📄 许可

本项目代码开源协议为 **[Business Source License 1.1](./LICENSE)** © Zkeq。

- 可以查看、修改、再分发，以及**非生产**使用
- **禁止**将本软件或其修改版上架任何应用商店，**禁止**出售或作为商业产品对外提供
- 生产使用须向权利人取得商业授权：`admin@icodeq.com`
- 本版本自 **2030-08-19** 起改为 Apache License 2.0

菜谱原文来自 [HowToCook](https://github.com/Anduin2017/HowToCook)（The Unlicense），不受本仓库 BSL 约束。
