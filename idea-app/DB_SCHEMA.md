# DB_SCHEMA.md — 点子 App 数据库设计

> 供 Trea IDE / Codex / WorkBuddy 读取  
> 数据库：PostgreSQL 16+  
| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| username | VARCHAR(20) UNIQUE | |
| password_hash | VARCHAR(255) | bcrypt |
| bio | VARCHAR(50) | 一句话简介 |
| dark_mode | BOOLEAN DEFAULT FALSE | |
| forkable | BOOLEAN DEFAULT TRUE | 是否允许他人fork |
| created_at | TIMESTAMPTZ | |

```sql
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    bio         VARCHAR(50) DEFAULT '',
    dark_mode   BOOLEAN DEFAULT FALSE,
    forkable    BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 2. ideas — 点子表

点子是核心实体。一个点子可能属于多个仓库（通过vault_items），但只有一条ideas记录。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| content | VARCHAR(300) | 点子文本 |
| color_hex | CHAR(7) | 从COLOR_POOL随机分配 |
| source | VARCHAR(20) | ugc/pgc/today_spark/fork/merge |
| author_id | UUID FK → users(id) | 产生者 |
| border_style | VARCHAR(10) | gold-thin(自己产生) / none(收集的) |
| fork_count | INT DEFAULT 0 | 被fork总数（热度） |
| is_forkable | BOOLEAN DEFAULT TRUE | |
| ai_assisted | BOOLEAN DEFAULT FALSE | 是否AI辅助生成 |
| evolved_from | VARCHAR(20) NULL | 演化角度（substitute/adapt/...） |
| status | VARCHAR(10) DEFAULT 'active' | active/fading/faded |
| last_fork_at | TIMESTAMPTZ | 最后被fork时间 |
| last_touch_at | TIMESTAMPTZ | 最后被触碰时间（查看/fork/碰撞/演化） |
| created_at | TIMESTAMPTZ | |

```sql
CREATE TABLE ideas (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content      VARCHAR(300) NOT NULL,
    color_hex    CHAR(7) NOT NULL,
    source       VARCHAR(20) NOT NULL CHECK (source IN ('ugc','pgc','today_spark','fork','merge','evolve')),
    author_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    border_style VARCHAR(10) DEFAULT 'none' CHECK (border_style IN ('gold-thin','none')),
    fork_count   INT DEFAULT 0,
    is_forkable  BOOLEAN DEFAULT TRUE,
    ai_assisted  BOOLEAN DEFAULT FALSE,
    evolved_from VARCHAR(20) NULL,
    status       VARCHAR(10) DEFAULT 'active' CHECK (status IN ('active','fading','faded')),
    last_fork_at TIMESTAMPTZ,
    last_touch_at TIMESTAMPTZ DEFAULT NOW(),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ideas_author ON ideas(author_id);
CREATE INDEX idx_ideas_fork_count ON ideas(fork_count DESC);
CREATE INDEX idx_ideas_last_fork ON ideas(last_fork_at DESC);
CREATE INDEX idx_ideas_status ON ideas(status);
```

---

## 3. vault_items — 仓库关联表

用户仓库中的点子。一个点子可以在多个用户的仓库中。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users(id) | |
| idea_id | UUID FK → ideas(id) | |
| is_producer | BOOLEAN | TRUE=自己产生的(金边), FALSE=收集的(无边) |
| added_at | TIMESTAMPTZ | 入仓库时间 |
| last_touch_at | TIMESTAMPTZ | 最后触碰时间（用于自然淡出） |

```sql
CREATE TABLE vault_items (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idea_id       UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    is_producer   BOOLEAN NOT NULL DEFAULT FALSE,
    added_at      TIMESTAMPTZ DEFAULT NOW(),
    last_touch_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, idea_id)
);

CREATE INDEX idx_vault_user ON vault_items(user_id);
CREATE INDEX idx_vault_touch ON vault_items(last_touch_at);
```

---

## 4. fork_relations — Fork关系表

点子之间的fork/merge/evolve关系。这是谱系图的核心。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| child_id | UUID FK → ideas(id) | 衍生点子 |
| parent_id | UUID FK → ideas(id) | 原始点子 |
| relation_type | VARCHAR(10) | fork（1对1）/ merge（1对多，碰撞）/ evolve（演化） |
| angle | VARCHAR(20) NULL | 演化角度（仅evolve类型） |
| created_at | TIMESTAMPTZ | |

```sql
CREATE TABLE fork_relations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    child_id      UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    parent_id     UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    relation_type VARCHAR(10) NOT NULL CHECK (relation_type IN ('fork','merge','evolve')),
    angle         VARCHAR(20) NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fork_child ON fork_relations(child_id);
CREATE INDEX idx_fork_parent ON fork_relations(parent_id);
```

---

## 5. spark_questions — 今日一点题目表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| date | DATE UNIQUE | 题目日期 |
| question | TEXT | 题目内容 |
| type | VARCHAR(20) | random_word/analogy/constraint/reverse_question |
| created_at | TIMESTAMPTZ | |

```sql
CREATE TABLE spark_questions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date       DATE UNIQUE NOT NULL,
    question   TEXT NOT NULL,
    type       VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. spark_drafts — 草稿表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users(id) | |
| question_id | UUID FK → spark_questions(id) | |
| content | TEXT | 草稿内容 |
| expires_at | TIMESTAMPTZ | 当日23:59:59 |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

```sql
CREATE TABLE spark_drafts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES spark_questions(id) ON DELETE CASCADE,
    content     TEXT DEFAULT '',
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, question_id)
);

CREATE INDEX idx_draft_expiry ON spark_drafts(expires_at);
```

---

## 7. spark_submissions — 今日一点提交表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users(id) | |
| question_id | UUID FK → spark_questions(id) | |
| idea_id | UUID FK → ideas(id) | 提交后生成的点子 |
| submitted_at | TIMESTAMPTZ | |

```sql
CREATE TABLE spark_submissions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id  UUID NOT NULL REFERENCES spark_questions(id) ON DELETE CASCADE,
    idea_id      UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, question_id)  -- 每日每人只能提交一次
);
```

---

## 8. notifications — 通知表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users(id) | 接收者 |
| type | VARCHAR(20) | forked/collected/spark_updated |
| content | VARCHAR(200) | 通知文案 |
| idea_id | UUID NULL | 相关点子 |
| actor_id | UUID NULL | 触发者 |
| read | BOOLEAN DEFAULT FALSE | |
| created_at | TIMESTAMPTZ | |

```sql
CREATE TABLE notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       VARCHAR(20) NOT NULL,
    content    VARCHAR(200) NOT NULL,
    idea_id    UUID REFERENCES ideas(id) ON DELETE SET NULL,
    actor_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    read       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notif_user ON notifications(user_id, read);
```

---

## 9. audit_logs — 审核日志表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| idea_id | UUID NULL | 相关点子（审核通过后创建） |
| content_snapshot | TEXT | 被审核内容快照 |
| result | VARCHAR(10) | pass/reject |
| reason | VARCHAR(200) | 不通过原因 |
| auditor | VARCHAR(10) | ai/human |
| created_at | TIMESTAMPTZ | |

```sql
CREATE TABLE audit_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idea_id          UUID REFERENCES ideas(id) ON DELETE SET NULL,
    content_snapshot TEXT NOT NULL,
    result           VARCHAR(10) NOT NULL CHECK (result IN ('pass','reject')),
    reason           VARCHAR(200),
    auditor          VARCHAR(10) NOT NULL CHECK (auditor IN ('ai','human')),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_result ON audit_logs(result);
```

---

## 10. 关键查询

### 10.1 主页探索（90%随机 + 10%近30天热门）

```sql
-- 10% 热门：近30天fork数Top
WITH hot_ideas AS (
    SELECT id, color_hex, fork_count,
           ROW_NUMBER() OVER (ORDER BY fork_count DESC) as rn
    FROM ideas
    WHERE status = 'active'
      AND last_fork_at > NOW() - INTERVAL '30 days'
    ORDER BY fork_count DESC
    LIMIT :hot_count  -- = ceil(limit * 0.1)
),
-- 90% 随机
random_ideas AS (
    SELECT id, color_hex, fork_count
    FROM ideas
    WHERE status = 'active'
      AND id NOT IN (SELECT id FROM hot_ideas)
    ORDER BY RANDOM()
    LIMIT :random_count  -- = limit - hot_count
)
SELECT * FROM (
    SELECT * FROM hot_ideas
    UNION ALL
    SELECT * FROM random_ideas
) AS combined
ORDER BY RANDOM();  -- 最终打乱顺序
```

### 10.2 谱系图（2层：父+子）

```sql
-- 查询某个点子的父节点和子节点
-- 父节点
SELECT i.id, i.color_hex, i.content, u.username,
       fr.relation_type, fr.angle
FROM fork_relations fr
JOIN ideas i ON i.id = fr.parent_id
LEFT JOIN users u ON u.id = i.author_id
WHERE fr.child_id = :idea_id;

-- 子节点
SELECT i.id, i.color_hex, i.content, u.username,
       fr.relation_type, fr.angle
FROM fork_relations fr
JOIN ideas i ON i.id = fr.child_id
LEFT JOIN users u ON u.id = i.author_id
WHERE fr.parent_id = :idea_id
ORDER BY fr.created_at DESC
LIMIT 10;
```

### 10.3 完整谱系树（未来扩展，递归CTE）

```sql
-- 递归查询所有祖先
WITH RECURSIVE ancestors AS (
    SELECT i.id, i.content, i.color_hex, fr.relation_type, 1 as depth
    FROM fork_relations fr
    JOIN ideas i ON i.id = fr.parent_id
    WHERE fr.child_id = :idea_id
    UNION ALL
    SELECT i.id, i.content, i.color_hex, fr.relation_type, a.depth + 1
    FROM fork_relations fr
    JOIN ideas i ON i.id = fr.parent_id
    JOIN ancestors a ON fr.child_id = a.id
    WHERE a.depth < 10  -- 防止无限递归
)
SELECT * FROM ancestors ORDER BY depth;

-- 递归查询所有后代
WITH RECURSIVE descendants AS (
    SELECT i.id, i.content, i.color_hex, fr.relation_type, 1 as depth
    FROM fork_relations fr
    JOIN ideas i ON i.id = fr.child_id
    WHERE fr.parent_id = :idea_id
    UNION ALL
    SELECT i.id, i.content, i.color_hex, fr.relation_type, d.depth + 1
    FROM fork_relations fr
    JOIN ideas i ON i.id = fr.child_id
    JOIN descendants d ON fr.parent_id = d.id
    WHERE d.depth < 10
)
SELECT * FROM descendants ORDER BY depth;
```

### 10.4 仓库圆圈列表（含状态）

```sql
SELECT i.id, i.color_hex, i.fork_count, i.status,
       vi.is_producer, vi.last_touch_at,
       vi.is_producer AS border_style  -- true='gold-thin', false='none'
FROM vault_items vi
JOIN ideas i ON i.id = vi.idea_id
WHERE vi.user_id = :user_id
  AND i.status != 'faded'
ORDER BY vi.last_touch_at DESC
LIMIT :limit OFFSET :offset;
```

### 10.5 个人主页（他人视角）

```sql
-- 该用户仓库所有点子（自己产生的+收集的）
SELECT i.id, i.color_hex, i.fork_count,
       vi.is_producer AS border_style
FROM vault_items vi
JOIN ideas i ON i.id = vi.idea_id
WHERE vi.user_id = :user_id
  AND i.status != 'faded'
ORDER BY vi.added_at DESC;

-- 统计
SELECT
    COUNT(*) FILTER (WHERE vi.is_producer = true) AS produced,
    COUNT(*) FILTER (WHERE vi.is_producer = false) AS collected,
    (SELECT COUNT(*) FROM fork_relations fr
     JOIN ideas i ON i.id = fr.parent_id
     WHERE i.author_id = :user_id) AS forked_by_others,
    (SELECT COUNT(*) FROM fork_relations fr
     JOIN ideas i ON i.id = fr.child_id
     WHERE i.author_id = :user_id) AS forked_others
FROM vault_items vi
WHERE vi.user_id = :user_id;
```

### 10.6 自然淡出检查（定时任务）

```sql
-- 更新status为fading（7天未触碰）
UPDATE ideas
SET status = 'fading'
WHERE id IN (
    SELECT i.id
    FROM vault_items vi
    JOIN ideas i ON i.id = vi.idea_id
    WHERE i.status = 'active'
      AND vi.last_touch_at < NOW() - INTERVAL '7 days'
);

-- 更新status为faded（8天未触碰→移出仓库）
DELETE FROM vault_items
WHERE last_touch_at < NOW() - INTERVAL '8 days';

-- 物理删除未被fork的faded点子
DELETE FROM ideas
WHERE status = 'faded'
  AND id NOT IN (SELECT parent_id FROM fork_relations
                 UNION
                 SELECT child_id FROM fork_relations);
```

---

## 11. 初始数据

### 11.1 PGC冷启动内容
```sql
-- 批量插入PGC点子（来源：HN高赞/Kickstarter经典/创新案例库）
INSERT INTO ideas (content, color_hex, source, author_id, border_style, ai_assisted)
VALUES
    ('用蚁群算法优化城市配送...', '#FF6B6B', 'pgc', NULL, 'none', false),
    ('用蜘蛛网结构设计独居老人监测网...', '#4ECDC4', 'pgc', NULL, 'none', false),
    -- ... 500-1000条
;
```

### 11.2 今日一点题库（预生成30天）
```sql
INSERT INTO spark_questions (date, question, type) VALUES
    ('2026-07-08', '如果手机没有屏幕会怎样？', 'reverse_question'),
    ('2026-07-09', '用『蜘蛛网』为独居老人设计一个产品', 'constraint'),
    ('2026-07-10', '电梯', 'random_word'),
    -- ... 30天
;
```

---

## 12. Redis 缓存策略

| Key | TTL | 说明 |
|---|---|---|
| `explore:page:{offset}` | 5min | 主页探索结果缓存 |
| `idea:detail:{id}` | 10min | 点子详情缓存 |
| `user:vault:{user_id}` | 5min | 仓库列表缓存 |
| `spark:today` | 24h | 今日题目缓存 |
| `spark:draft:{user_id}:{date}` | 到当日23:59 | 草稿缓存 |
| `user:stats:{user_id}` | 10min | 用户统计缓存 |
| `notifications:unread:{user_id}` | 1min | 未读通知数缓存 |

---

## 13. 数据库初始化

```sql
-- 创建数据库
CREATE DATABASE dianzi_app ENCODING 'UTF8';

-- 启用UUID扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 按上述顺序执行所有CREATE TABLE
-- 按上述顺序执行所有CREATE INDEX

-- 初始化PGC内容（见11.1）
-- 初始化30天今日一点题库（见11.2）
```
