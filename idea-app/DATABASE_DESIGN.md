# 点子 App 数据库设计文档

> 版本：v1.0  
> 日期：2026-07-08  
> 适用范围：PostgreSQL 16+（生产）/ SQLite 3.40+（开发兜底）  
> ORM：SQLAlchemy 2.0 (async)  

---

## 目录

- [1. 数据库设计概述](#1-数据库设计概述)
  - [1.1 设计目标](#11-设计目标)
  - [1.2 设计方法](#12-设计方法)
  - [1.3 设计步骤](#13-设计步骤)
- [2. 需求分析](#2-需求分析)
  - [2.1 信息需求](#21-信息需求)
  - [2.2 处理需求](#22-处理需求)
  - [2.3 安全性与完整性需求](#23-安全性与完整性需求)
- [3. 概念结构设计](#3-概念结构设计)
  - [3.1 实体识别](#31-实体识别)
  - [3.2 E-R 图](#32-e-r-图)
  - [3.3 实体联系说明](#33-实体联系说明)
- [4. 逻辑结构设计](#4-逻辑结构设计)
  - [4.1 关系模式汇总](#41-关系模式汇总)
  - [4.2 表结构详细定义](#42-表结构详细定义)
  - [4.3 约束条件](#43-约束条件)
  - [4.4 索引设计](#44-索引设计)
  - [4.5 规范化分析](#45-规范化分析)
- [5. 物理结构设计](#5-物理结构设计)
  - [5.1 存储引擎与字符集](#51-存储引擎与字符集)
  - [5.2 存取方法选择](#52-存取方法选择)
  - [5.3 物理存储估算](#53-物理存储估算)
- [6. 数据库实施](#6-数据库实施)
  - [6.1 数据库初始化](#61-数据库初始化)
  - [6.2 初始数据（种子）](#62-初始数据种子)
  - [6.3 数据库迁移](#63-数据库迁移)
- [7. 数据库运行和维护](#7-数据库运行和维护)
  - [7.1 定时任务](#71-定时任务)
  - [7.2 缓存策略](#72-缓存策略)
  - [7.3 关键查询](#73-关键查询)
- [8. 数据字典](#8-数据字典)

---

## 1. 数据库设计概述

### 1.1 设计目标

为"点子 App"——一个创意激发社区——提供一个高效、可扩展、易维护的数据存储基础设施。该数据库需支持以下核心业务：

| 业务模块 | 数据需求 |
|---|---|
| 用户系统 | 注册、登录、个人设置、大模型配置 |
| 点子发布 | UGC/PGC 内容存储、15 色随机分配、金边/无边区分 |
| 探索页 | 90% 随机 + 10% 近 30 天热门，真随机布局 |
| 仓库 | 个人收藏管理、自然淡出（7 天 fading → 8 天 faded） |
| 谱系图 | fork / merge（碰撞）/ evolve（演化）关系链 |
| 今日一点 | 每日题目、草稿、提交 |
| 通知系统 | fork / collected / spark_updated 通知 |
| 内容审核 | 违禁词匹配 + AI 语义审核、审核日志 |

### 1.2 设计方法

采用**规范设计法**（基于 E-R 模型的数据库设计方法），遵循"自顶向下、分层实现、逐步求精"的原则，分为需求分析→概念设计→逻辑设计→物理设计→实施→运行维护六个阶段。

### 1.3 设计步骤

| 阶段 | 产出物 |
|---|---|
| 需求分析 | 数据字典、数据流图 |
| 概念结构设计 | E-R 图 |
| 逻辑结构设计 | 关系模式、表结构、约束、索引 |
| 物理结构设计 | 存储引擎、存取方法、存储估算 |
| 数据库实施 | DDL 脚本、种子数据、迁移脚本 |
| 运行维护 | 定时任务、缓存策略、性能监控 |

---

## 2. 需求分析

### 2.1 信息需求

系统需存储以下核心信息：

1. **用户信息**：用户名、密码哈希、简介、暗色模式、fork 权限、大模型 API 配置
2. **点子信息**：内容、颜色、来源、作者、边框样式、热度、状态、演化角度
3. **仓库关系**：用户与点子的收藏关系、是否为产出者、最后触碰时间
4. **谱系关系**：点子之间的 fork / merge / evolve 关系
5. **今日一点**：每日题目、用户草稿、用户提交
6. **通知**：fork / collected / spark_updated 等通知
7. **审核日志**：内容快照、审核结果、审核者
8. **违禁词库**：敏感词、级别

### 2.2 处理需求

| 处理场景 | 频率 | 性能要求 |
|---|---|---|
| 探索页加载（25 个圆圈） | 高频 | < 200ms |
| 点子详情查看 | 高频 | < 100ms |
| 发布点子 | 中频 | < 500ms（含审核） |
| 仓库列表 | 中频 | < 200ms |
| 谱系图查询（2 层） | 低频 | < 300ms |
| 今日一点提交 | 低频 | < 500ms |
| 通知列表 | 中频 | < 100ms |
| 自然淡出检查（定时） | 每日 1 次 | < 10s |

### 2.3 安全性与完整性需求

| 类别 | 要求 |
|---|---|
| 身份认证 | JWT Bearer Token，密码 bcrypt 哈希 |
| 数据完整性 | 外键约束 + CHECK 约束 + UNIQUE 约束 |
| 软删除策略 | 点子用 status='faded' 软删除；仓库物理删除 |
| 级联策略 | 用户删除→CASCADE 仓库/草稿/提交/通知；点子删除→SET NULL 外键 |
| API Key 保护 | 数据库明文存储（MVP），回读时脱敏（sk-***1234） |

---

## 3. 概念结构设计

### 3.1 实体识别

通过对信息需求的分析，识别出以下实体：

| 实体 | 说明 | 主码 |
|---|---|---|
| User（用户） | 系统的使用者 | id (UUID) |
| Idea（点子） | 核心内容实体 | id (UUID) |
| VaultItem（仓库项） | 用户与点子的收藏关系 | id (UUID) |
| ForkRelation（谱系关系） | 点子之间的衍生关系 | id (UUID) |
| SparkQuestion（今日一点题目） | 每日题目 | id (UUID) |
| SparkDraft（草稿） | 用户对题目的草稿 | id (UUID) |
| SparkSubmission（提交） | 用户对题目的正式提交 | id (UUID) |
| Notification（通知） | 系统通知 | id (UUID) |
| AuditLog（审核日志） | 内容审核记录 | id (UUID) |
| BannedWord（违禁词） | 敏感词库 | id (INT) |

### 3.2 E-R 图

```
┌──────────┐       ┌──────────┐       ┌──────────────┐
│   User   │       │   Idea   │       │  VaultItem   │
│──────────│       │──────────│       │──────────────│
│ id (PK)  │◄──┐   │ id (PK)  │◄──┐   │ id (PK)      │
│ username │   │   │ content  │   │   │ user_id (FK) │──► User
│ password │   │   │ color_hex│   │   │ idea_id (FK) │──► Idea
│ bio      │   │   │ source   │   │   │ is_producer  │
│ ...      │   │   │ ...      │   │   │ last_touch   │
└──────────┘   │   └──────────┘   │   └──────────────┘
     │         │        │         │
     │         │        │         │
     │         │   ┌────┴─────────┴────┐
     │         │   │   ForkRelation    │
     │         │   │───────────────────│
     │         │   │ id (PK)           │
     │         │   │ child_id (FK) ───►│ Idea
     │         │   │ parent_id (FK) ──►│ Idea
     │         │   │ relation_type     │
     │         │   │ angle             │
     │         │   └───────────────────┘
     │         │
     │         │   ┌──────────────────┐       ┌────────────────┐
     │         ├──►│  SparkSubmission │◄──────│  SparkDraft    │
     │         │   │──────────────────│       │────────────────│
     │         │   │ id (PK)          │       │ id (PK)        │
     │         │   │ user_id (FK) ───►│ User  │ user_id (FK) ─►│ User
     │         │   │ question_id (FK) │       │ question_id    │
     │         │   │ idea_id (FK) ───►│ Idea  │ content        │
     │         │   │ submitted_at     │       │ expires_at     │
     │         │   └──────────────────┘       └────────────────┘
     │         │                                    │
     │         │           ┌────────────────────────┘
     │         │           │
     │         │   ┌───────┴────────────┐
     │         │   │  SparkQuestion     │
     │         │   │────────────────────│
     │         │   │ id (PK)            │
     │         │   │ date (UNIQUE)      │
     │         │   │ question           │
     │         │   │ type               │
     │         │   └────────────────────┘
     │         │
     │         │   ┌──────────────────┐
     │         ├──►│  Notification    │
     │         │   │──────────────────│
     │         │   │ id (PK)          │
     │         │   │ user_id (FK) ───►│ User
     │         │   │ type             │
     │         │   │ idea_id (FK) ───►│ Idea
     │         │   │ actor_id (FK) ──►│ User
     │         │   │ read             │
     │         │   └──────────────────┘
     │         │
     │         │   ┌──────────────────┐
     │         ├──►│    AuditLog      │
     │         │   │──────────────────│
     │         │   │ id (PK)          │
     │         │   │ idea_id (FK) ───►│ Idea
     │         │   │ content_snapshot │
     │         │   │ result           │
     │         │   │ auditor          │
     │         │   └──────────────────┘
     │         │
     │         │   ┌──────────────────┐
     │         └──►│   BannedWord     │
     │             │──────────────────│
     │             │ id (PK, AUTO)    │
     │             │ word (UNIQUE)    │
     │             │ level            │
     │             └──────────────────┘
     │
     └── author_id (FK, SET NULL)
```

### 3.3 实体联系说明

| 联系 | 类型 | 说明 |
|---|---|---|
| User → Idea | 1:N | 一个用户可产生多个点子（author_id） |
| User → VaultItem | 1:N | 一个用户有多个仓库项 |
| Idea → VaultItem | 1:N | 一个点子可在多个用户的仓库中 |
| User ↔ Idea (via VaultItem) | M:N | 多对多收藏关系 |
| Idea → ForkRelation (child) | 1:N | 一个点子可有多条子关系 |
| Idea → ForkRelation (parent) | 1:N | 一个点子可有多条父关系 |
| Idea ↔ Idea (via ForkRelation) | M:N | 点子间多对多衍生关系 |
| User → SparkDraft | 1:N | 一个用户有多条草稿 |
| User → SparkSubmission | 1:N | 一个用户有多条提交 |
| SparkQuestion → SparkDraft | 1:N | 一个题目有多条草稿 |
| SparkQuestion → SparkSubmission | 1:N | 一个题目有多条提交 |
| User → Notification | 1:N | 一个用户接收多条通知 |
| User → Notification (actor) | 1:N | 一个用户可触发多条通知 |
| Idea → AuditLog | 1:N | 一个点子可有多条审核记录 |

---

## 4. 逻辑结构设计

### 4.1 关系模式汇总

将 E-R 图转换为关系模式，主码用 <u>下划线</u> 标出，外码用 *斜体* 标出：

1. **users**(<u>id</u>, username, password_hash, bio, dark_mode, forkable, llm_api_url, llm_api_key, created_at)
2. **ideas**(<u>id</u>, content, color_hex, source, *author_id*, border_style, fork_count, is_forkable, ai_assisted, evolved_from, status, last_fork_at, last_touch_at, created_at)
3. **vault_items**(<u>id</u>, *user_id*, *idea_id*, is_producer, last_touch_at, created_at)
4. **fork_relations**(<u>id</u>, *child_id*, *parent_id*, relation_type, angle, created_at)
5. **spark_questions**(<u>id</u>, date, question, type, created_at)
6. **spark_drafts**(<u>id</u>, *user_id*, *question_id*, content, expires_at, created_at, updated_at)
7. **spark_submissions**(<u>id</u>, *user_id*, *question_id*, *idea_id*, submitted_at)
8. **notifications**(<u>id</u>, *user_id*, type, content, *idea_id*, *actor_id*, read, created_at)
9. **audit_logs**(<u>id</u>, *idea_id*, content_snapshot, result, reason, auditor, created_at)
10. **banned_words**(<u>id</u>, word, level)

### 4.2 表结构详细定义

#### 4.2.1 users — 用户表

存储用户账号信息与个人设置。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | UUID | PK | gen_random_uuid() | 用户唯一标识 |
| username | VARCHAR(20) | UNIQUE, NOT NULL, INDEX | — | 用户名 |
| password_hash | VARCHAR(255) | NOT NULL | — | bcrypt 密码哈希 |
| bio | VARCHAR(50) | — | '' | 一句话简介 |
| dark_mode | BOOLEAN | — | FALSE | 暗色模式开关 |
| forkable | BOOLEAN | — | TRUE | 是否允许他人 fork |
| llm_api_url | VARCHAR(255) | — | '' | 大模型 API 地址（OpenAI 兼容） |
| llm_api_key | VARCHAR(255) | — | '' | 大模型 API 密钥（明文存储，回读脱敏） |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 创建时间 |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    bio           VARCHAR(50) DEFAULT '',
    dark_mode     BOOLEAN DEFAULT FALSE,
    forkable      BOOLEAN DEFAULT TRUE,
    llm_api_url   VARCHAR(255) DEFAULT '',
    llm_api_key   VARCHAR(255) DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username);
```

---

#### 4.2.2 ideas — 点子表

核心内容实体，存储所有 UGC/PGC 点子。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | UUID | PK | gen_random_uuid() | 点子唯一标识 |
| content | VARCHAR(300) | NOT NULL | — | 点子文本内容 |
| color_hex | VARCHAR(7) | NOT NULL | — | 15 色池随机分配的十六进制颜色 |
| source | VARCHAR(20) | NOT NULL, CHECK | — | 来源：ugc/pgc/today_spark/fork/merge/evolve |
| author_id | UUID | FK → users(id), NULL | NULL | 产生者（PGC 为系统账号） |
| border_style | VARCHAR(10) | CHECK | 'none' | 边框：gold-thin（自产）/ none（收集） |
| fork_count | INTEGER | — | 0 | 被 fork 总数（热度指标） |
| is_forkable | BOOLEAN | — | TRUE | 是否允许 fork |
| ai_assisted | BOOLEAN | — | FALSE | 是否 AI 辅助生成 |
| evolved_from | VARCHAR(20) | NULL | NULL | 演化角度（substitute/adapt/modify/put_to_other_use/eliminate/reverse） |
| status | VARCHAR(10) | CHECK | 'active' | 状态：active/fading/faded/rejected |
| last_fork_at | TIMESTAMPTZ | NULL | NULL | 最后被 fork 时间 |
| last_touch_at | TIMESTAMPTZ | NOT NULL | NOW() | 最后触碰时间（查看/fork/碰撞/演化） |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 创建时间 |

**CHECK 约束：**

| 约束名 | 条件 |
|---|---|
| ck_ideas_source | source IN ('ugc','pgc','today_spark','fork','merge','evolve') |
| ck_ideas_border | border_style IN ('gold-thin','none') |
| ck_ideas_status | status IN ('active','fading','faded','rejected') |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE ideas (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content       VARCHAR(300) NOT NULL,
    color_hex     VARCHAR(7) NOT NULL,
    source        VARCHAR(20) NOT NULL,
    author_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    border_style  VARCHAR(10) DEFAULT 'none',
    fork_count    INTEGER DEFAULT 0,
    is_forkable   BOOLEAN DEFAULT TRUE,
    ai_assisted   BOOLEAN DEFAULT FALSE,
    evolved_from  VARCHAR(20) NULL,
    status        VARCHAR(10) DEFAULT 'active',
    last_fork_at  TIMESTAMPTZ NULL,
    last_touch_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_ideas_source CHECK (source IN ('ugc','pgc','today_spark','fork','merge','evolve')),
    CONSTRAINT ck_ideas_border CHECK (border_style IN ('gold-thin','none')),
    CONSTRAINT ck_ideas_status CHECK (status IN ('active','fading','faded','rejected'))
);

CREATE INDEX idx_ideas_author     ON ideas(author_id);
CREATE INDEX idx_ideas_fork_count ON ideas(fork_count DESC);
CREATE INDEX idx_ideas_last_fork  ON ideas(last_fork_at DESC);
CREATE INDEX idx_ideas_status     ON ideas(status);
```

---

#### 4.2.3 vault_items — 仓库关联表

用户仓库中的点子收藏记录，一个点子可在多个用户仓库中。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | UUID | PK | gen_random_uuid() | 仓库项唯一标识 |
| user_id | UUID | FK → users(id), NOT NULL, INDEX | — | 仓库所属用户 |
| idea_id | UUID | FK → ideas(id), NOT NULL | — | 收藏的点子 |
| is_producer | BOOLEAN | NOT NULL | FALSE | TRUE=自产（金边）/ FALSE=收集（无边） |
| last_touch_at | TIMESTAMPTZ | NOT NULL, INDEX | NOW() | 最后触碰时间（用于自然淡出） |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 入仓库时间 |

**UNIQUE 约束：**

| 约束名 | 字段 | 说明 |
|---|---|---|
| uq_vault_user_idea | (user_id, idea_id) | 同一用户不能重复收藏同一 点子 |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE vault_items (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idea_id       UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    is_producer   BOOLEAN NOT NULL DEFAULT FALSE,
    last_touch_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_vault_user_idea UNIQUE (user_id, idea_id)
);

CREATE INDEX idx_vault_user  ON vault_items(user_id);
CREATE INDEX idx_vault_touch ON vault_items(last_touch_at);
```

---

#### 4.2.4 fork_relations — 谱系关系表

点子之间的衍生关系，是谱系图的核心。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | UUID | PK | gen_random_uuid() | 关系唯一标识 |
| child_id | UUID | FK → ideas(id), NOT NULL, INDEX | — | 衍生点子 |
| parent_id | UUID | FK → ideas(id), NOT NULL, INDEX | — | 原始点子 |
| relation_type | VARCHAR(10) | NOT NULL, CHECK | — | 关系类型：fork/merge/evolve |
| angle | VARCHAR(20) | NULL | NULL | 演化角度（仅 evolve 类型） |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 关系建立时间 |

**CHECK 约束：**

| 约束名 | 条件 |
|---|---|
| ck_fork_relation_type | relation_type IN ('fork','merge','evolve') |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE fork_relations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    child_id      UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    parent_id     UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    relation_type VARCHAR(10) NOT NULL,
    angle         VARCHAR(20) NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_fork_relation_type CHECK (relation_type IN ('fork','merge','evolve'))
);

CREATE INDEX idx_fork_child  ON fork_relations(child_id);
CREATE INDEX idx_fork_parent ON fork_relations(parent_id);
```

---

#### 4.2.5 spark_questions — 今日一点题目表

每日发布的创意激发题目。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | UUID | PK | gen_random_uuid() | 题目唯一标识 |
| date | DATE | UNIQUE, NOT NULL | — | 题目日期（每天唯一） |
| question | TEXT | NOT NULL | — | 题目内容 |
| type | VARCHAR(20) | NOT NULL | — | 题型：random_word/analogy/constraint/reverse_question |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 创建时间 |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE spark_questions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date       DATE UNIQUE NOT NULL,
    question   TEXT NOT NULL,
    type       VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

#### 4.2.6 spark_drafts — 草稿表

用户对今日一点题目的草稿，带过期时间。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | UUID | PK | gen_random_uuid() | 草稿唯一标识 |
| user_id | UUID | FK → users(id), NOT NULL | — | 草稿所属用户 |
| question_id | UUID | FK → spark_questions(id), NOT NULL | — | 关联题目 |
| content | TEXT | — | '' | 草稿内容 |
| expires_at | TIMESTAMPTZ | NOT NULL, INDEX | — | 过期时间（当日 23:59:59） |
| created_at | TIMESTAMPTZ | — | NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | — | NOW() | 更新时间（自动 onupdate） |

**UNIQUE 约束：**

| 约束名 | 字段 | 说明 |
|---|---|---|
| uq_draft_user_question | (user_id, question_id) | 每人每题只能有一份草稿 |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE spark_drafts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES spark_questions(id) ON DELETE CASCADE,
    content     TEXT DEFAULT '',
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_draft_user_question UNIQUE (user_id, question_id)
);

CREATE INDEX idx_draft_expiry ON spark_drafts(expires_at);
```

---

#### 4.2.7 spark_submissions — 今日一点提交表

用户对今日一点题目的正式提交，提交后生成点子。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | UUID | PK | gen_random_uuid() | 提交唯一标识 |
| user_id | UUID | FK → users(id), NOT NULL | — | 提交用户 |
| question_id | UUID | FK → spark_questions(id), NOT NULL | — | 关联题目 |
| idea_id | UUID | FK → ideas(id), NOT NULL | — | 提交后生成的点子 |
| submitted_at | TIMESTAMPTZ | — | NOW() | 提交时间 |

**UNIQUE 约束：**

| 约束名 | 字段 | 说明 |
|---|---|---|
| uq_submission_user_question | (user_id, question_id) | 每人每题只能提交一次 |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE spark_submissions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id  UUID NOT NULL REFERENCES spark_questions(id) ON DELETE CASCADE,
    idea_id      UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_submission_user_question UNIQUE (user_id, question_id)
);
```

---

#### 4.2.8 notifications — 通知表

系统通知，支持 fork / collected / spark_updated 等类型。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | UUID | PK | gen_random_uuid() | 通知唯一标识 |
| user_id | UUID | FK → users(id), NOT NULL, INDEX | — | 接收者 |
| type | VARCHAR(20) | NOT NULL | — | 类型：forked/collected/spark_updated |
| content | VARCHAR(200) | NOT NULL | — | 通知文案 |
| idea_id | UUID | FK → ideas(id), NULL | NULL | 相关点子 |
| actor_id | UUID | FK → users(id), NULL | NULL | 触发者 |
| read | BOOLEAN | — | FALSE | 是否已读 |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 创建时间 |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       VARCHAR(20) NOT NULL,
    content    VARCHAR(200) NOT NULL,
    idea_id    UUID REFERENCES ideas(id) ON DELETE SET NULL,
    actor_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    read       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notif_user ON notifications(user_id, read);
```

---

#### 4.2.9 audit_logs — 审核日志表

内容审核记录，保留内容快照供追溯。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | UUID | PK | gen_random_uuid() | 日志唯一标识 |
| idea_id | UUID | FK → ideas(id), NULL | NULL | 相关点子（审核通过后创建） |
| content_snapshot | TEXT | NOT NULL | — | 被审核内容快照 |
| result | VARCHAR(10) | NOT NULL | — | 审核结果：pass/reject |
| reason | VARCHAR(200) | NULL | NULL | 不通过原因 |
| auditor | VARCHAR(10) | NOT NULL | — | 审核者：ai/human |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | 审核时间 |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE audit_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idea_id          UUID REFERENCES ideas(id) ON DELETE SET NULL,
    content_snapshot TEXT NOT NULL,
    result           VARCHAR(10) NOT NULL,
    reason           VARCHAR(200),
    auditor          VARCHAR(10) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_result ON audit_logs(result);
```

---

#### 4.2.10 banned_words — 违禁词表

敏感词库，用于内容审核的违禁词匹配。

| 字段名 | 数据类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| id | SERIAL (INT) | PK, AUTO INCREMENT | — | 违禁词唯一标识 |
| word | VARCHAR(100) | UNIQUE, NOT NULL | — | 违禁词文本 |
| level | VARCHAR(10) | — | 'high' | 级别：high/medium/low |

**DDL (PostgreSQL)：**

```sql
CREATE TABLE banned_words (
    id    SERIAL PRIMARY KEY,
    word  VARCHAR(100) UNIQUE NOT NULL,
    level VARCHAR(10) DEFAULT 'high'
);
```

---

### 4.3 约束条件

#### 4.3.1 主键约束

| 表 | 主键字段 | 类型 |
|---|---|---|
| users | id | UUID |
| ideas | id | UUID |
| vault_items | id | UUID |
| fork_relations | id | UUID |
| spark_questions | id | UUID |
| spark_drafts | id | UUID |
| spark_submissions | id | UUID |
| notifications | id | UUID |
| audit_logs | id | UUID |
| banned_words | id | SERIAL (INT) |

#### 4.3.2 外键约束

| 子表 | 字段 | 父表 | ON DELETE | 说明 |
|---|---|---|---|---|
| ideas | author_id | users | SET NULL | 作者删除后点子保留 |
| vault_items | user_id | users | CASCADE | 用户删除→仓库清空 |
| vault_items | idea_id | ideas | CASCADE | 点子删除→仓库项清空 |
| fork_relations | child_id | ideas | CASCADE | 子点子删除→关系删除 |
| fork_relations | parent_id | ideas | CASCADE | 父点子删除→关系删除 |
| spark_drafts | user_id | users | CASCADE | 用户删除→草稿清空 |
| spark_drafts | question_id | spark_questions | CASCADE | 题目删除→草稿清空 |
| spark_submissions | user_id | users | CASCADE | 用户删除→提交清空 |
| spark_submissions | question_id | spark_questions | CASCADE | 题目删除→提交清空 |
| spark_submissions | idea_id | ideas | CASCADE | 点子删除→提交清空 |
| notifications | user_id | users | CASCADE | 用户删除→通知清空 |
| notifications | idea_id | ideas | SET NULL | 点子删除→通知保留 |
| notifications | actor_id | users | SET NULL | 触发者删除→通知保留 |
| audit_logs | idea_id | ideas | SET NULL | 点子删除→日志保留 |

#### 4.3.3 CHECK 约束

| 约束名 | 表 | 条件 |
|---|---|---|
| ck_ideas_source | ideas | source IN ('ugc','pgc','today_spark','fork','merge','evolve') |
| ck_ideas_border | ideas | border_style IN ('gold-thin','none') |
| ck_ideas_status | ideas | status IN ('active','fading','faded','rejected') |
| ck_fork_relation_type | fork_relations | relation_type IN ('fork','merge','evolve') |

#### 4.3.4 UNIQUE 约束

| 约束名 | 表 | 字段 | 说明 |
|---|---|---|---|
| — | users | username | 用户名全局唯一 |
| — | spark_questions | date | 每天题目唯一 |
| — | banned_words | word | 违禁词不重复 |
| uq_vault_user_idea | vault_items | (user_id, idea_id) | 不重复收藏 |
| uq_draft_user_question | spark_drafts | (user_id, question_id) | 每人每题一份草稿 |
| uq_submission_user_question | spark_submissions | (user_id, question_id) | 每人每题一次提交 |

---

### 4.4 索引设计

| 索引名 | 表 | 字段 | 类型 | 用途 |
|---|---|---|---|---|
| idx_users_username | users | username | UNIQUE | 登录查询 |
| idx_ideas_author | ideas | author_id | B-Tree | 查用户产生的点子 |
| idx_ideas_fork_count | ideas | fork_count DESC | B-Tree | 热门排序 |
| idx_ideas_last_fork | ideas | last_fork_at DESC | B-Tree | 近 30 天热门查询 |
| idx_ideas_status | ideas | status | B-Tree | 过滤 active/fading/faded |
| idx_vault_user | vault_items | user_id | B-Tree | 查用户仓库 |
| idx_vault_touch | vault_items | last_touch_at | B-Tree | 自然淡出检查 |
| idx_fork_child | fork_relations | child_id | B-Tree | 查父节点 |
| idx_fork_parent | fork_relations | parent_id | B-Tree | 查子节点 |
| idx_draft_expiry | spark_drafts | expires_at | B-Tree | 清理过期草稿 |
| idx_notif_user | notifications | (user_id, read) | B-Tree | 查未读通知 |
| idx_audit_result | audit_logs | result | B-Tree | 审核统计 |

---

### 4.5 规范化分析

本数据库设计满足 **第三范式（3NF）**：

| 范式 | 满足条件 | 说明 |
|---|---|---|
| 1NF | 所有字段都是原子值 | ✅ 无嵌套属性 |
| 2NF | 非主属性完全依赖于主码 | ✅ 所有表主码为单字段 UUID |
| 3NF | 非主属性不传递依赖于主码 | ✅ 无传递依赖 |

**反规范化设计**（为查询性能做的妥协）：

| 字段 | 说明 | 理由 |
|---|---|---|
| ideas.fork_count | 冗余了 fork_relations 的 COUNT | 避免热门查询时 JOIN + COUNT |
| ideas.last_fork_at | 冗余了 fork_relations 的 MAX(created_at) | 避免近 30 天热门查询时 JOIN |
| ideas.last_touch_at | 冗余了 vault_items 的 MAX(last_touch_at) | 避免淡出检查时 JOIN |
| ideas.status | 冗余了淡出状态 | 避免探索页查询时计算淡出 |

---

## 5. 物理结构设计

### 5.1 存储引擎与字符集

| 配置项 | PostgreSQL（生产） | SQLite（开发） |
|---|---|---|
| 存储引擎 | 默认（heap） | 默认（B-tree） |
| 字符集 | UTF8 | UTF8 |
| 时区 | TIMESTAMPTZ（带时区） | TEXT（ISO8601 带时区） |
| UUID 生成 | gen_random_uuid() | Python uuid.uuid4() |
| 主键策略 | UUID v4 | UUID v4（存储为 36 字符字符串） |

### 5.2 存取方法选择

| 查询场景 | 存取方法 | 对应索引 |
|---|---|---|
| 按用户名登录 | B-Tree 等值查询 | idx_users_username |
| 探索页热门排序 | B-Tree 降序扫描 | idx_ideas_fork_count |
| 近 30 天热门 | B-Tree 范围 + 降序 | idx_ideas_last_fork |
| 状态过滤 | B-Tree 等值查询 | idx_ideas_status |
| 用户仓库列表 | B-Tree 等值查询 | idx_vault_user |
| 淡出检查 | B-Tree 范围查询 | idx_vault_touch |
| 谱系图查询 | B-Tree 等值查询 | idx_fork_child / idx_fork_parent |
| 未读通知 | B-Tree 复合查询 | idx_notif_user (user_id, read) |

### 5.3 物理存储估算

| 表 | 预估行数（1 年） | 平均行大小 | 预估存储 |
|---|---|---|---|
| users | 10,000 | 300 B | 3 MB |
| ideas | 100,000 | 500 B | 50 MB |
| vault_items | 500,000 | 150 B | 75 MB |
| fork_relations | 200,000 | 150 B | 30 MB |
| spark_questions | 365 | 200 B | 0.1 MB |
| spark_drafts | 50,000 | 400 B | 20 MB |
| spark_submissions | 30,000 | 150 B | 5 MB |
| notifications | 1,000,000 | 200 B | 200 MB |
| audit_logs | 100,000 | 400 B | 40 MB |
| banned_words | 100 | 120 B | 0.01 MB |
| **合计** | — | — | **~420 MB** |

> 索引额外占用约 30%（~130 MB），总预估 ~550 MB。

---

## 6. 数据库实施

### 6.1 数据库初始化

**PostgreSQL（生产）：**

```sql
CREATE DATABASE dianzi_app ENCODING 'UTF8';
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 按以下顺序执行所有 CREATE TABLE（先父表后子表）：
-- 1. users
-- 2. ideas
-- 3. vault_items
-- 4. fork_relations
-- 5. spark_questions
-- 6. spark_drafts
-- 7. spark_submissions
-- 8. notifications
-- 9. audit_logs
-- 10. banned_words

-- 然后执行所有 CREATE INDEX
```

**SQLite（开发兜底）：**

通过 SQLAlchemy `Base.metadata.create_all()` 自动建表，无需手动 DDL。详见 [database.py](file:///f:/treaFiles/Ideas/ideas/idea-app/backend/database.py) 的 `_init_sqlite_schema()` 函数。

### 6.2 初始数据（种子）

系统启动时自动插入以下种子数据（幂等）：

| 数据 | 数量 | 说明 |
|---|---|---|
| PGC 系统账号 | 1 | username=dianzi_pgc |
| PGC 点子 | 30 | 冷启动内容池 |
| 今日一点题库 | 30 | 预生成 30 天题目 |
| 违禁词库 | 14 | 高级别敏感词 |

种子数据详见 [database.py](file:///f:/treaFiles/Ideas/ideas/idea-app/backend/database.py) 的 `_seed_initial_data()` 函数。

### 6.3 数据库迁移

**SQLite 轻量迁移**：由于 `create_all` 不会 ALTER 已存在的表，系统提供了 `_migrate_sqlite_columns()` 函数自动检测并补充新列。

当前已注册的迁移：

| 表 | 列 | DDL |
|---|---|---|
| users | llm_api_url | VARCHAR(255) DEFAULT '' |
| users | llm_api_key | VARCHAR(255) DEFAULT '' |

迁移逻辑在 `create_all` 之后、`_seed_initial_data` 之前执行，确保 schema 就绪后再插入数据。

---

## 7. 数据库运行和维护

### 7.1 定时任务

通过 APScheduler 注册的定时任务：

| 任务 | 执行时间 | 说明 |
|---|---|---|
| 清理过期草稿 | 每日 00:00 | 删除 `spark_drafts` 中 `expires_at < NOW()` 的记录 |
| 自然淡出检查 | 每日 01:00 | 1. 7 天未触碰 → status='fading' <br> 2. 8 天未触碰 → 删除 vault_items <br> 3. 未被 fork 的 faded 点子 → 物理删除 |

**淡出检查 SQL：**

```sql
-- 1. 7 天未触碰 → fading
UPDATE ideas
SET status = 'fading'
WHERE id IN (
    SELECT i.id
    FROM vault_items vi
    JOIN ideas i ON i.id = vi.idea_id
    WHERE i.status = 'active'
      AND vi.last_touch_at < NOW() - INTERVAL '7 days'
);

-- 2. 8 天未触碰 → 移出仓库
DELETE FROM vault_items
WHERE last_touch_at < NOW() - INTERVAL '8 days';

-- 3. 未被 fork 的 faded 点子 → 物理删除
DELETE FROM ideas
WHERE status = 'faded'
  AND id NOT IN (
      SELECT parent_id FROM fork_relations
      UNION
      SELECT child_id FROM fork_relations
  );
```

---

### 7.2 缓存策略

| Redis Key | TTL | 说明 |
|---|---|---|
| `explore:page:{offset}` | 5min | 主页探索结果缓存 |
| `idea:detail:{id}` | 10min | 点子详情缓存 |
| `user:vault:{user_id}` | 5min | 仓库列表缓存 |
| `spark:today` | 24h | 今日题目缓存 |
| `spark:draft:{user_id}:{date}` | 到当日 23:59 | 草稿缓存 |
| `user:stats:{user_id}` | 10min | 用户统计缓存 |
| `notifications:unread:{user_id}` | 1min | 未读通知数缓存 |

> 开发环境下 Redis 不可用时，自动退化为内存字典缓存。

---

### 7.3 关键查询

#### 7.3.1 主页探索（90% 随机 + 10% 近 30 天热门）

```sql
WITH hot_ideas AS (
    SELECT id, color_hex, fork_count
    FROM ideas
    WHERE status = 'active'
      AND last_fork_at >= NOW() - INTERVAL '30 days'
    ORDER BY fork_count DESC
    LIMIT :hot_count  -- ceil(limit * 0.1)
),
random_ideas AS (
    SELECT id, color_hex, fork_count
    FROM ideas
    WHERE status = 'active'
      AND id NOT IN (SELECT id FROM hot_ideas)
    ORDER BY RANDOM()
    LIMIT :random_count  -- limit - hot_count
)
SELECT * FROM (
    SELECT * FROM hot_ideas
    UNION ALL
    SELECT * FROM random_ideas
) AS combined
ORDER BY RANDOM();
```

#### 7.3.2 谱系图（2 层：父 + 子）

```sql
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

#### 7.3.3 仓库圆圈列表

```sql
SELECT i.id, i.color_hex, i.fork_count, i.status,
       vi.is_producer, vi.last_touch_at
FROM vault_items vi
JOIN ideas i ON i.id = vi.idea_id
WHERE vi.user_id = :user_id
  AND i.status != 'faded'
ORDER BY vi.last_touch_at DESC
LIMIT :limit OFFSET :offset;
```

#### 7.3.4 个人主页统计

```sql
SELECT
    COUNT(*) FILTER (WHERE vi.is_producer = true)  AS produced,
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

---

## 8. 数据字典

### 8.1 枚举值定义

| 字段 | 表 | 枚举值 | 说明 |
|---|---|---|---|
| source | ideas | ugc | 用户原创 |
| source | ideas | pgc | 官方精选 |
| source | ideas | today_spark | 今日一点 |
| source | ideas | fork | Fork 衍生 |
| source | ideas | merge | 碰撞合并 |
| source | ideas | evolve | 演化 |
| border_style | ideas | gold-thin | 金边（自产） |
| border_style | ideas | none | 无边（收集） |
| status | ideas | active | 活跃 |
| status | ideas | fading | 淡出中（7 天未触碰） |
| status | ideas | faded | 已淡出（8 天未触碰） |
| status | ideas | rejected | 审核拒绝 |
| relation_type | fork_relations | fork | Fork |
| relation_type | fork_relations | merge | 碰撞合并 |
| relation_type | fork_relations | evolve | 演化 |
| type | spark_questions | random_word | 随机词 |
| type | spark_questions | analogy | 类比 |
| type | spark_questions | constraint | 约束 |
| type | spark_questions | reverse_question | 逆向提问 |
| result | audit_logs | pass | 审核通过 |
| result | audit_logs | reject | 审核拒绝 |
| auditor | audit_logs | ai | AI 审核 |
| auditor | audit_logs | human | 人工审核 |
| type | notifications | forked | 被他人 fork |
| type | notifications | collected | 被他人收集 |
| type | notifications | spark_updated | 今日一点更新 |

### 8.2 颜色池（15 色）

```
#FF6B6B  #4ECDC4  #FFE66D  #FF8E72  #6EC5E9
#C5E8A0  #7FD6A1  #FFB347  #B5A8E8  #83A6ED
#A8D8D8  #FF9EBB  #C9B1FF  #FFB6C1  #D4A5A5
```

### 8.3 SAMPER 演化角度

| 角度 | 说明 |
|---|---|
| substitute | 替代 |
| adapt | 适应 |
| modify | 修改 |
| put_to_other_use | 改作他用 |
| eliminate | 消除 |
| reverse | 反转 |

---

## 附录：表关系速查

```
users (1) ──────< (N) ideas
  │                   │
  │ (1)               │ (1)
  │                   │
  ▼ (N)               ▼ (N)
vault_items (M) ──> (1) ideas
  │                   │
  │                   │
  ▼ (N)               ▼ (N)
spark_drafts    fork_relations (M) ──> (1) ideas [child]
spark_submissions                    (M) ──> (1) ideas [parent]
notifications                   audit_logs
banned_words (独立)
spark_questions (独立，被 drafts/submissions 引用)
```

---

> **文档维护说明**：本文档基于实际代码（[models/](file:///f:/treaFiles/Ideas/ideas/idea-app/backend/models)）生成，如代码变更请同步更新本文档。
