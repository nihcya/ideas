-- ============================================================
-- 点子 App 数据库 Schema
-- PostgreSQL 16+
-- 按 DB_SCHEMA.md 实现
-- ============================================================

-- 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- gen_random_uuid

-- ============================================================
-- 1. users — 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    bio           VARCHAR(50) DEFAULT '',
    dark_mode     BOOLEAN DEFAULT FALSE,
    forkable      BOOLEAN DEFAULT TRUE,
    llm_api_url   VARCHAR(255) DEFAULT '',
    llm_api_key   VARCHAR(255) DEFAULT '',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ============================================================
-- 2. ideas — 点子表
-- ============================================================
CREATE TABLE IF NOT EXISTS ideas (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content       VARCHAR(300) NOT NULL,
    color_hex     CHAR(7) NOT NULL,
    source        VARCHAR(20) NOT NULL CHECK (source IN ('ugc','pgc','today_spark','fork','merge','evolve')),
    author_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    border_style  VARCHAR(10) DEFAULT 'none' CHECK (border_style IN ('gold-thin','none')),
    fork_count    INT DEFAULT 0,
    is_forkable   BOOLEAN DEFAULT TRUE,
    ai_assisted   BOOLEAN DEFAULT FALSE,
    evolved_from  VARCHAR(20) NULL,
    status        VARCHAR(10) DEFAULT 'active' CHECK (status IN ('active','fading','faded','rejected')),
    last_fork_at  TIMESTAMPTZ,
    last_touch_at TIMESTAMPTZ DEFAULT NOW(),
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    publication_status VARCHAR(16) NOT NULL DEFAULT 'draft'
        CHECK (publication_status IN ('draft','published','archived')),
    visibility VARCHAR(16) NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private','public')),
    license_code VARCHAR(32),
    license_text_snapshot TEXT,
    license_version VARCHAR(32),
    allow_fork BOOLEAN NOT NULL DEFAULT FALSE,
    published_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    legacy_license_review_status VARCHAR(16) NOT NULL DEFAULT 'not_required'
        CHECK (legacy_license_review_status IN ('not_required','pending','confirmed','expired')),
    legacy_license_review_notified_at TIMESTAMPTZ,
    legacy_license_reviewed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ideas_author    ON ideas(author_id);
CREATE INDEX IF NOT EXISTS idx_ideas_fork_count ON ideas(fork_count DESC);
CREATE INDEX IF NOT EXISTS idx_ideas_last_fork ON ideas(last_fork_at DESC);
CREATE INDEX IF NOT EXISTS idx_ideas_status    ON ideas(status);
CREATE INDEX IF NOT EXISTS idx_ideas_publication_visibility ON ideas(publication_status, visibility, status);
CREATE INDEX IF NOT EXISTS idx_ideas_legacy_license_review ON ideas(legacy_license_review_status);
CREATE INDEX IF NOT EXISTS idx_ideas_created   ON ideas(created_at DESC);

-- ============================================================
-- 3. vault_items — 仓库关联表
-- ============================================================
CREATE TABLE IF NOT EXISTS vault_items (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idea_id       UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    is_producer   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_touch_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, idea_id)
);

CREATE INDEX IF NOT EXISTS idx_vault_user  ON vault_items(user_id);
CREATE INDEX IF NOT EXISTS idx_vault_touch ON vault_items(last_touch_at);

-- ============================================================
-- 4. fork_relations — Fork关系表（谱系图核心）
-- ============================================================
CREATE TABLE IF NOT EXISTS fork_relations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    child_id      UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    parent_id     UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    relation_type VARCHAR(10) NOT NULL CHECK (relation_type IN ('fork','merge','evolve')),
    angle         VARCHAR(20) NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fork_child  ON fork_relations(child_id);
CREATE INDEX IF NOT EXISTS idx_fork_parent ON fork_relations(parent_id);

-- ============================================================
-- 5. spark_questions — 今日一点题目表
-- ============================================================
CREATE TABLE IF NOT EXISTS spark_questions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date       DATE UNIQUE NOT NULL,
    question   TEXT NOT NULL,
    type       VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 6. spark_drafts — 草稿表
-- ============================================================
CREATE TABLE IF NOT EXISTS spark_drafts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES spark_questions(id) ON DELETE CASCADE,
    content     TEXT DEFAULT '',
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_draft_expiry ON spark_drafts(expires_at);

-- ============================================================
-- 7. spark_submissions — 今日一点提交表
-- ============================================================
CREATE TABLE IF NOT EXISTS spark_submissions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id  UUID NOT NULL REFERENCES spark_questions(id) ON DELETE CASCADE,
    idea_id      UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, question_id)
);

-- ============================================================
-- 8. notifications — 通知表
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       VARCHAR(20) NOT NULL,
    content    VARCHAR(200) NOT NULL,
    idea_id    UUID REFERENCES ideas(id) ON DELETE SET NULL,
    actor_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    read       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, read);

-- ============================================================
-- 9. audit_logs — 审核日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idea_id          UUID REFERENCES ideas(id) ON DELETE SET NULL,
    content_snapshot TEXT NOT NULL,
    result           VARCHAR(10) NOT NULL CHECK (result IN ('pass','reject')),
    reason           VARCHAR(200),
    auditor          VARCHAR(10) NOT NULL CHECK (auditor IN ('ai','human')),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_result ON audit_logs(result);

-- ============================================================
-- 10. banned_words — 违禁词库
-- ============================================================
CREATE TABLE IF NOT EXISTS banned_words (
    id    SERIAL PRIMARY KEY,
    word  VARCHAR(100) UNIQUE NOT NULL,
    level VARCHAR(10) NOT NULL DEFAULT 'high'  -- high=直接拒, low=AI复审
);

-- ============================================================

-- ============================================================
-- 11. idea_access_grants — direct private Idea invitations
-- ============================================================
CREATE TABLE IF NOT EXISTS idea_access_grants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idea_id     UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(16) NOT NULL DEFAULT 'viewer'
                CHECK (role IN ('contributor','viewer')),
    status      VARCHAR(16) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','accepted','declined','revoked')),
    invited_by  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    invited_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(idea_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_idea_access_grants_user_status
    ON idea_access_grants(user_id, status);
CREATE INDEX IF NOT EXISTS idx_idea_access_grants_idea_status
    ON idea_access_grants(idea_id, status);

-- 完成
-- ============================================================
