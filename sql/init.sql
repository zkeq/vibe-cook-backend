-- Vibe Cook Backend 数据库初始化脚本 (SQLite)
-- 由 db.py 在首次启动时自动执行,幂等(IF NOT EXISTS)

-- ==================== 用户表 ====================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,                                  -- 手机号
    password TEXT,                                      -- bcrypt 加密(仅管理员/编辑)
    nickname TEXT,                                      -- 昵称
    avatar TEXT,                                        -- 头像URL
    role TEXT NOT NULL DEFAULT 'user'
        CHECK (role IN ('user', 'editor', 'admin')),    -- 角色
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'banned')),         -- 状态
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);

-- updated_at 自动更新(SQLite 无 ON UPDATE,用触发器)
CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
AFTER UPDATE ON users FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = datetime('now', 'localtime') WHERE id = OLD.id;
END;

-- 默认管理员(密码 admin123 的 bcrypt hash);已存在则保持 admin 角色
INSERT INTO users (phone, password, nickname, role, status) VALUES
('admin', '$2b$12$U3oYui4KWBf7d.O7CO9ahuKYPCDG39lSRnzXuUcaRLslUT5mjXxJO', '系统管理员', 'admin', 'active')
ON CONFLICT(phone) DO UPDATE SET role = 'admin';

-- ==================== 食谱表 ====================
-- 结构化食谱完整数据存于 data(JSON 文本),与前端 lib/types.ts 的 Recipe 契约一致。
-- 顶层冗余 title/category/cover_image,便于列表查询,避免每次解析 JSON。
CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,                                -- slug,如 xihongshi-chaodan
    title TEXT NOT NULL,                                -- 菜名
    category TEXT,                                      -- 分类
    cover_image TEXT,                                   -- 封面图URL
    data TEXT NOT NULL,                                 -- 完整结构化食谱(JSON 文本)
    status TEXT NOT NULL DEFAULT 'published'
        CHECK (status IN ('draft', 'published')),       -- 状态
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category);
CREATE INDEX IF NOT EXISTS idx_recipes_status   ON recipes(status);

CREATE TRIGGER IF NOT EXISTS trg_recipes_updated_at
AFTER UPDATE ON recipes FOR EACH ROW
BEGIN
    UPDATE recipes SET updated_at = datetime('now', 'localtime') WHERE id = OLD.id;
END;
