# API_SPEC.md — 点子 App 后端 API 规格

> 供 Trea IDE / Codex / WorkBuddy 读取  
> 后端：FastAPI + PostgreSQL + Redis + DeepSeek  
> Base URL: `http://localhost:8000/api`  
> 所有请求/响应均为 JSON  
> 认证：Bearer Token（JWT）

---

## 1. 认证

### POST /auth/register
注册新用户。
```json
// Request
{ "username": "string(3-20)", "password": "string(8+)", "bio": "string(0-50)" }
// Response 201
{ "user_id": "uuid", "username": "string", "token": "jwt_string" }
// Error 400: 用户名已存在
```

### POST /auth/login
```json
// Request
{ "username": "string", "password": "string" }
// Response 200
{ "user_id": "uuid", "username": "string", "token": "jwt_string" }
// Error 401: 用户名或密码错误
```

---

## 2. 点子

### GET /ideas/explore
主页探索页。返回一批圆圈（90%随机 + 10%近30天fork数Top）。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| limit | int | 25 | 每次返回数量 |
| offset | int | 0 | 分页偏移 |

```json
// Response 200
{
  "circles": [
    {
      "id": "uuid",
      "color_hex": "#FF6B6B",
      "size_score": 0.65,        // 0-1, 决定圆圈渲染大小
      "is_own": false,           // 是否为自己产生的
      "fork_count": 12           // 被fork数（用于大小计算）
    }
  ],
  "has_more": true
}
```

**注意**：此接口不返回点子内容，只返回圆圈渲染所需数据。内容需点击后通过 /ideas/{id} 获取。

---

### GET /ideas/{id}
点子详情页。返回完整内容 + 谱系图（2层）。

```json
// Response 200
{
  "id": "uuid",
  "content": "string(≤300字)",
  "color_hex": "#FF6B6B",
  "source": "ugc|pgc|today_spark|fork|merge",
  "author": {
    "id": "uuid",
    "username": "string",
    "bio": "string"
  },
  "created_at": "2026-07-08T12:00:00Z",
  "fork_count": 12,
  "is_forkable": true,
  "is_in_vault": false,         // 当前用户是否已收集
  "lineage": {
    "parents": [                 // 父节点（0-2个）
      { "id": "uuid", "color_hex": "#4ECDC4", "author": "用户Z", "title": "蚂蚁觅食行为" }
    ],
    "children": [                // 子节点（被fork的，最多返回10个）
      { "id": "uuid", "color_hex": "#FFE66D", "author": "用户B", "title": "蚁群配送优化" }
    ]
  }
}
// Error 404: 点子不存在
```

---

### POST /ideas
发布新点子（直接发布，非fork/碰撞/演化）。

```json
// Request (需认证)
{ "content": "string(≤300字)" }
// Response 201
{
  "id": "uuid",
  "content": "string",
  "color_hex": "#随机分配",     // 后端从12-16色池真随机分配
  "source": "ugc",
  "author_id": "uuid",
  "created_at": "2026-07-08T12:00:00Z",
  "border_style": "gold-thin"   // 自己产生的=金边
}
// Error 400: 内容为空或超300字
// Error 403: 内容审核不通过（违禁词）
```

**后端处理流程**：
1. 内容审核（AI+违禁词库）→ 不通过返回403
2. 随机分配color_hex（从COLOR_POOL中Random.choice）
3. 写入ideas表
4. 写入vault_items表（author自己的仓库）
5. 返回完整点子

---

### POST /ideas/fork
Fork一个点子（联想引导后提交）。

```json
// Request (需认证)
{
  "parent_id": "uuid",           // 被fork的原点子
  "content": "string(≤300字)"   // 用户的联想内容
}
// Response 201
{
  "id": "uuid",                  // 新点子ID
  "parent_id": "uuid",
  "content": "string",
  "color_hex": "#随机",
  "source": "fork",
  "border_style": "gold-thin"
}
// Error 404: 原点子不存在
// Error 403: 原点子is_forkable=false
// Error 400: 内容审核不通过
```

**后端处理流程**：
1. 验证parent_id存在且is_forkable=true
2. 内容审核
3. 创建新点子（source="fork"）
4. 写入fork_relations表（child_id=新点子, parent_id=原点子）
5. 写入vault_items（新点子入fork者仓库）
6. 更新原点子fork_count
7. 发通知给原点子作者
8. 返回新点子

---

### POST /ideas/collide
碰撞两个点子，AI生成3个结合方案。

```json
// Request (需认证)
{
  "idea_a_id": "uuid",
  "idea_b_id": "uuid"
}
// Response 200
{
  "suggestions": [
    { "content": "string(≤300字)", "type": "practical" },
    { "content": "string(≤300字)", "type": "cross_domain" },
    { "content": "string(≤300字)", "type": "unconventional" }
  ]
}
// Error 404: 点子不存在
// Error 429: 今日次数超限（MVP不限制，后期启用）
```

**后端处理流程**：
1. 获取两个点子内容
2. 调用DeepSeek（temperature=0.9, 见DEEPSEEK_PROMPTS）
3. 解析AI响应，提取3个方案
4. 返回给前端预览（不入库）

---

### POST /ideas/collide/confirm
用户选定碰撞方案后确认入仓库。

```json
// Request (需认证)
{
  "idea_a_id": "uuid",
  "idea_b_id": "uuid",
  "content": "string(≤300字)",       // 用户选定的方案（可编辑）
  "ai_assisted": true
}
// Response 201
{
  "id": "uuid",
  "parent_ids": ["uuid_a", "uuid_b"],
  "source": "merge",
  "border_style": "gold-thin"
}
```

---

### POST /ideas/evolve
演化一个点子，选SAMPER角度，AI生成3个变体。

```json
// Request (需认证)
{
  "idea_id": "uuid",
  "angle": "substitute|adapt|modify|put_to_other_use|eliminate|reverse"
}
// Response 200
{
  "variants": [
    { "content": "string(≤300字)", "distance": "near" },
    { "content": "string(≤300字)", "distance": "medium" },
    { "content": "string(≤300字)", "distance": "bold" }
  ]
}
```

**SAMPER角度说明**：
- substitute: 这个点子里什么可以被替换？
- adapt: 能从其他领域借鉴什么？
- modify: 放大或缩小某个方面？
- put_to_other_use: 这个点子还能用在哪里？
- eliminate: 去掉什么会让它更好？
- reverse: 反过来想会怎样？

---

### POST /ideas/evolve/confirm
用户选定演化变体后确认入仓库。

```json
// Request (需认证)
{
  "parent_id": "uuid",
  "angle": "string",
  "content": "string(≤300字)",
  "ai_assisted": true
}
// Response 201
{
  "id": "uuid",
  "parent_id": "uuid",
  "evolved_from": "angle_string",
  "source": "evolve",
  "border_style": "gold-thin"
}
```

---

## 3. 仓库

### GET /vault
获取当前用户的仓库圆圈列表。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| limit | int | 50 |  |
| offset | int | 0 |  |

```json
// Response 200
{
  "stats": {
    "produced": 12,       // 自己产生的（金边）
    "collected": 28,      // 收集的（无边）
    "forked_by_others": 47 // 被别人fork的总数
  },
  "circles": [
    {
      "id": "uuid",
      "color_hex": "#FF6B6B",
      "size_score": 0.5,
      "border_style": "gold-thin|none",
      "status": "active|fading|faded",
      "last_touch_at": "2026-07-01T12:00:00Z"
    }
  ],
  "has_more": false
}
```

---

### DELETE /vault/{idea_id}
将点子从仓库移出。

```json
// Response 200
{ "removed": true, "idea_id": "uuid" }
// Error 404: 点子不在仓库中
```

**后端逻辑**：
- 删除vault_items中的记录
- 如果点子未被任何人fork → 物理删除ideas表记录
- 如果点子被fork过 → 保留ideas表记录（谱系图需要），仅从当前用户仓库移出

---

### POST /vault/{idea_id}/collect
收集一个别人的点子到仓库。

```json
// Request (需认证)
{}
// Response 201
{ "collected": true, "idea_id": "uuid" }
// Error 409: 已在仓库中
```

---

## 4. 今日一点

### GET /spark/today
获取今日题目。

```json
// Response 200
{
  "date": "2026-07-08",
  "question": "如果手机没有屏幕会怎样？",
  "type": "reverse_question",      // random_word|analogy|constraint|reverse_question
  "duration_seconds": 180,
  "has_draft": false,              // 是否已有草稿
  "submitted": false               // 是否已提交
}
// Error 410: 今日题目已过期（超过23:59）
```

---

### POST /spark/draft
保存草稿（自动触发或手动触发）。

```json
// Request
{ "content": "string(≤300字)" }
// Response 200
{
  "saved": true,
  "expires_at": "2026-07-08T23:59:59Z",   // 当日23:59过期
  "first_save": true                      // 首次保存时前端弹窗提示
}
```

---

### POST /spark/submit
提交今日一点入仓库。

```json
// Request
{ "content": "string(≤300字)" }
// Response 201
{
  "id": "uuid",
  "source": "today_spark",
  "border_style": "gold-thin",
  "color_hex": "#随机"
}
// Error 400: 内容审核不通过
// Error 410: 今日已过期，不能补做
// Error 409: 今日已提交过
```

---

## 5. 个人主页

### GET /users/{id}
获取用户公开主页（思维森林）。

```json
// Response 200
{
  "id": "uuid",
  "username": "string",
  "bio": "string",
  "stats": {
    "produced": 12,
    "collected": 28,
    "forked_by_others": 47,
    "forked_others": 8
  },
  "circles": [                     // 该用户仓库所有点子（金边+无边混合）
    {
      "id": "uuid",
      "color_hex": "#FF6B6B",
      "size_score": 0.6,
      "border_style": "gold-thin|none"
    }
  ]
}
```

---

## 6. 通知

### GET /notifications
获取通知列表。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| limit | int | 20 |  |
| offset | int | 0 |  |

```json
// Response 200
{
  "notifications": [
    {
      "id": "uuid",
      "type": "forked|collected|spark_updated",
      "content": "用户B fork了你的『社区养老互助』",
      "idea_id": "uuid|null",
      "actor_id": "uuid|null",
      "created_at": "2026-07-08T10:00:00Z",
      "read": false
    }
  ],
  "unread_count": 3
}
```

---

### POST /notifications/read
标记通知为已读。

```json
// Request
{ "notification_ids": ["uuid1", "uuid2"] }
// Response 200
{ "marked_read": 2 }
```

---

## 7. 设置

### GET /settings
```json
// Response 200
{
  "dark_mode": false,
  "forkable": true,                // 是否允许他人fork我的点子
  "username": "string",
  "bio": "string"
}
```

### PUT /settings
```json
// Request
{ "dark_mode": false, "forkable": true, "bio": "string(≤50)" }
// Response 200
{ "updated": true }
```

---

## 8. 统一错误格式

```json
// 所有4xx/5xx错误
{
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "人类可读的错误描述"
  }
}
```

| HTTP | code | 场景 |
|---|---|---|
| 400 | CONTENT_TOO_LONG | 超过300字 |
| 400 | CONTENT_EMPTY | 内容为空 |
| 401 | UNAUTHORIZED | 未登录/token过期 |
| 403 | AUDIT_FAILED | 内容审核不通过 |
| 403 | FORK_DISABLED | 原点子不允许fork |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | ALREADY_EXISTS | 重复操作（如重复收集） |
| 410 | SPARK_EXPIRED | 今日一点已过期 |
| 429 | RATE_LIMITED | 超出每日次数限制（后期启用） |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

---

## 9. DeepSeek AI Prompt 模板

### 碰撞 Prompt
```
你是创意碰撞引擎。下面有两个点子，请生成3个把它们结合起来的新点子方案。

点子A：{content_a}
点子B：{content_b}

要求：
- 每个方案≤300字
- 不是简单拼接，而是找到两个点子的深层联结点
- 3个方案角度不同：
  1. practical（实用型，可落地执行）
  2. cross_domain（跨界型，引入第三个领域的视角）
  3. unconventional（反常规型，打破常识的非常规组合）

请严格按以下JSON格式返回：
{ "suggestions": [ {"content": "...", "type": "practical"}, ... ] }
```

### 演化 Prompt
```
你是创意演化引擎。下面是一个点子和一个SAMPER角度，请生成3个变体。

点子：{content}
角度：{angle}（{angle_description}）

要求：
- 每个变体≤300字
- 保留原点子的核心洞察，但在指定角度上有创新
- 3个变体不同程度的"远离原点子"：
  1. near（微调，保留大部分原内容）
  2. medium（明显变形，保留核心洞察）
  3. bold（大胆重构，只保留灵感种子）

请严格按以下JSON格式返回：
{ "variants": [ {"content": "...", "distance": "near"}, ... ] }
```

### 审核 Prompt
```
你是内容审核员。判断以下内容是否合规：
"{content}"

审核标准：
1. 不含违禁词（政治敏感/色情/暴力/诈骗/广告引流）
2. 不含人身攻击或辱骂
3. 不含垃圾信息（纯符号/重复字符/无意义内容）

请返回JSON：
{ "pass": true/false, "reason": "如果不通过，说明原因" }
```

---

## 10. 色彩池（后端常量）

```python
COLOR_POOL = [
    "#FF6B6B", "#FF8E72", "#FFB347", "#FFE66D", "#C5E8A0",
    "#7FD6A1", "#4ECDC4", "#6EC5E9", "#83A6ED", "#B5A8E8",
    "#C9B1FF", "#FFB6C1", "#FF9EBB", "#D4A5A5", "#A8D8D8",
]
# 15色，明度饱和度都有变化
# 分配方式：random.choice(COLOR_POOL)
# 禁止按内容哈希分配（会导致同色=同类的伪分类）
```
