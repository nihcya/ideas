# Trea IDE 环境配置与最优方法 — 点子 App

> 本文档供 Trea IDE / Codex / WorkBuddy 等 AI 辅助开发工具读取。  
> 项目：点子 App（创意激发社区）  
> 技术栈：Flutter + FastAPI + PostgreSQL + Redis + DeepSeek  
> 创建：2026-07-08

---

## 1. 环境搭建

### 1.1 Flutter 开发环境

```bash
# 1. 安装 Flutter SDK（推荐 3.24+）
# 下载地址：https://docs.flutter.dev/get-started/install
# 假设安装到 ~/flutter
export PATH="$HOME/flutter/bin:$PATH"

# 2. 验证安装
flutter doctor

# 3. 安装各平台工具链
# iOS: 需 Xcode 15+ + CocoaPods
# Android: 需 Android Studio + Android SDK

# 4. 创建项目
cd /home/z/my-project/idea-app
flutter create --org com.dianzi --project-name dianzi_app .
```

### 1.2 后端环境

```bash
# Python 3.11+
cd /home/z/my-project/idea-app/backend
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy asyncpg psycopg2-binary redis openai pydantic
```

### 1.3 Trea IDE 配置

1. **安装 Flutter 插件**：Trea IDE → 扩展 → 搜索 "Flutter" → 安装（Dart SDK 随 Flutter 插件自动安装）
2. **配置 Flutter SDK 路径**：Trea IDE → 设置 → 搜索 "flutter" → 设置 SDK path
3. **配置 Dart 分析器**：设置 → 搜索 "dart" → 启用 "Dart Analysis Server"
4. **配置保存时格式化**：设置 → 搜索 "format on save" → 启用
5. **启用热重载快捷键**：`Ctrl+S` 保存触发 Hot Reload

---

## 2. 项目结构

```
idea-app/
├── lib/                          # Flutter 前端
│   ├── main.dart                 # 入口
│   ├── app.dart                  # MaterialApp 配置
│   ├── models/                   # 数据模型
│   │   ├── idea.dart             # 点子模型
│   │   ├── user.dart             # 用户模型
│   │   └── fork_relation.dart    # fork关系
│   ├── services/                 # 网络服务
│   │   ├── api_client.dart       # HTTP客户端
│   │   ├── idea_service.dart     # 点子CRUD
│   │   ├── fork_service.dart     # fork操作
│   │   └── evolve_service.dart   # 碰撞+演化AI调用
│   ├── providers/                # 状态管理（Riverpod）
│   │   ├── idea_provider.dart
│   │   ├── vault_provider.dart
│   │   └── auth_provider.dart
│   ├── pages/                    # 页面
│   │   ├── home_page.dart        # 主页（圆圈海洋）
│   │   ├── vault_page.dart       # 仓库
│   │   ├── spark_page.dart       # 今日一点
│   │   ├── detail_page.dart      # 点子详情+谱系图
│   │   ├── profile_page.dart     # 个人主页
│   │   ├── create_page.dart      # 发布点子
│   │   ├── fork_page.dart        # Fork联想引导
│   │   ├── notice_page.dart      # 通知
│   │   └── settings_page.dart    # 设置
│   ├── widgets/                  # 可复用组件
│   │   ├── circle_canvas.dart    # ★核心：圆圈渲染(CustomPainter)
│   │   ├── circle_widget.dart    # 单个圆圈widget
│   │   ├── evolve_menu.dart      # 演化菜单(漫游式路径+震动)
│   │   ├── lineage_tree.dart     # 谱系图2层
│   │   └── idea_card.dart        # 点子卡片
│   ├── utils/                    # 工具
│   │   ├── colors.dart           # ★12-16色池真随机
│   │   ├── haptics.dart          # ★震动反馈封装
│   │   └── random_layout.dart    # ★伪随机圆圈布局算法
│   └── theme/                    # 主题
│       ├── light.dart
│       └── dark.dart
├── backend/                      # FastAPI 后端
│   ├── main.py                   # FastAPI入口
│   ├── models/                   # SQLAlchemy模型
│   ├── routers/                  # API路由
│   │   ├── ideas.py
│   │   ├── users.py
│   │   ├── fork.py
│   │   └── evolve.py             # 碰撞+演化AI接口
│   ├── services/                 # 业务逻辑
│   │   ├── deepseek_client.py    # DeepSeek API封装
│   │   ├── audit_service.py      # AI审核
│   │   └── spark_service.py      # 今日一点题库
│   └── db/                       # 数据库
│       ├── schema.sql            # DDL
│       └── migrations/
├── prototype/                    # 低保真原型（已完成）
│   └── index.html
├── 点子App_PRD_V1.0.pdf          # 正式PRD
├── DISCUSSION_NOTES.md           # 讨论纪要
├── TREA_CONTEXT.md               # ★本文件（Trea上下文）
├── API_SPEC.md                   # API规格
├── DB_SCHEMA.md                  # 数据库DDL
└── TECH_CONSTRAINTS.md           # 技术约束
```

---

## 3. 上下文包设计（Trea AI 一次性读取）

Trea IDE 的核心优势是 AI 辅助开发。以下文件应放在项目根目录，让 Trea AI 一次性读取全部上下文：

| 文件 | 作用 | 大小 |
|---|---|---|
| `TREA_CONTEXT.md`（本文件） | 项目总览+环境+结构+工作流 | ~5KB |
| `API_SPEC.md` | 所有API端点规格（请求/响应JSON） | ~4KB |
| `DB_SCHEMA.md` | 数据库DDL+索引+关系说明 | ~3KB |
| `TECH_CONSTRAINTS.md` | 技术约束清单（字体/色彩/动效/震动） | ~3KB |

**Trea AI 首次对话 prompt 模板：**
```
请阅读以下文件后开始开发：
1. TREA_CONTEXT.md — 项目总览和环境配置
2. API_SPEC.md — 后端API规格
3. DB_SCHEMA.md — 数据库结构
4. TECH_CONSTRAINTS.md — 技术约束
5. 点子App_PRD_V1.0.pdf — 完整PRD（如需详细信息）

阅读完成后，从 "第一步：项目初始化" 开始。
```

---

## 4. 技术约束（TECH_CONSTRAINTS.md 摘要）

### 4.1 圆圈渲染（★最核心）
- **使用 CustomPainter**，不要用 ListView/GridView
- 圆圈位置由 `random_layout.dart` 的伪随机算法生成
- 圆圈大小 = f(fork_count, 近期衰减)
- **颜色从12-16色池真随机分配**，禁止按内容哈希
- **圆圈上不显示任何文字**（方案C）
- 金边圆圈：`border: 3px solid #FFD700`（自己产生的）
- 无边圆圈：收集的别人的点子
- 浮动动效：`AnimationController` + `Curves.easeInOut` + 3秒周期 + 随机延迟
- 悬停放大：`ScaleTransition` + `BoxShadow`
- fork涟漪：`CustomPainter` + `RippleEffect`
- 淡出：`Opacity` + `AnimationController` 渐变

### 4.2 色彩系统
```dart
// utils/colors.dart
import 'dart:math';
final _rng = Random();
const COLOR_POOL = [
  '#FF6B6B', '#FF8E72', '#FFB347', '#FFE66D', '#C5E8A0',
  '#7FD6A1', '#4ECDC4', '#6EC5E9', '#83A6ED', '#B5A8E8',
  '#C9B1FF', '#FFB6C1', '#FF9EBB', '#D4A5A5', '#A8D8D8',
];
String randomColor() => COLOR_POOL[_rng.nextInt(COLOR_POOL.length)];
```

### 4.3 震动反馈
```dart
// utils/haptics.dart
import 'package:flutter/services.dart';
class Haptics {
  static void step() => HapticFeedback.lightImpact();      // 演化菜单步行
  static void select() => HapticFeedback.selectionClick();  // 选择圆圈
  static void fork() => HapticFeedback.mediumImpact();     // fork涟漪
}
```

### 4.4 状态管理
- **使用 Riverpod**（推荐，类型安全，测试友好）
- 核心Provider：`ideaProvider`、`vaultProvider`、`authProvider`
- 圆圈布局状态用 `StateNotifier` 管理

### 4.5 后端约束
- FastAPI + asyncpg（异步PostgreSQL驱动）
- fork关系查询用**递归CTE**（MVP够用，后期可迁移Neo4j）
- DeepSeek API：`openai` 包 + `base_url` 指向 DeepSeek
- AI审核：先发后审，异步审核，违规撤回
- 今日一点题目：每日0:00更新，存Redis缓存

---

## 5. API 规格摘要（API_SPEC.md 摘要）

### 5.1 点子 CRUD
```
POST   /api/ideas                    创建点子
GET    /api/ideas/home               主页圆圈（90%随机+10%近30天热门）
GET    /api/ideas/{id}               点子详情
GET    /api/ideas/vault              用户仓库圆圈
POST   /api/ideas/{id}/collect       收集到仓库
DELETE /api/ideas/{id}               从仓库移出（被fork的永久存在）
```

### 5.2 Fork
```
POST   /api/ideas/{id}/fork          Fork（联想引导→新点子）
GET    /api/ideas/{id}/lineage       谱系图（2层：父+子）
```

### 5.3 演化
```
POST   /api/ideas/collide            碰撞（输入2个点子ID→3个方案）
POST   /api/ideas/evolve             演化（输入1个点子ID+SAMPER角度→3个变体）
```

### 5.4 今日一点
```
GET    /api/spark/today              今日题目
POST   /api/spark/submit             提交（入仓库为金边圆圈）
POST   /api/spark/draft              保存草稿（23:59过期）
```

### 5.5 用户
```
GET    /api/users/{id}/profile       个人主页（所有点子=森林）
GET    /api/users/me/vault           我的仓库
```

---

## 6. 数据库 DDL 摘要（DB_SCHEMA.md 摘要）

```sql
-- 点子表
CREATE TABLE ideas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content     TEXT NOT NULL CHECK (length(content) <= 300),
    source      VARCHAR(20) NOT NULL,  -- ugc/pgc/today_spark/fork/collide/evolve
    author_id   UUID NOT NULL REFERENCES users(id),
    color_hex   VARCHAR(7) NOT NULL,   -- 真随机分配
    border_style VARCHAR(10) DEFAULT 'none',  -- none/gold
    forkable    BOOLEAN DEFAULT true,
    ai_assisted BOOLEAN DEFAULT false,
    evolved_from VARCHAR(20),  -- SAMPER角度
    created_at  TIMESTAMPTZ DEFAULT now(),
    last_fork_at TIMESTAMPTZ DEFAULT now()
);

-- Fork关系表（支持多父=碰撞）
CREATE TABLE fork_relations (
    child_id  UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    parent_id UUID NOT NULL REFERENCES ideas(id),
    relation  VARCHAR(20) NOT NULL,  -- fork/collide/evolve
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (child_id, parent_id)
);

-- 仓库表（用户收集+产生的点子）
CREATE TABLE vault_items (
    user_id   UUID NOT NULL REFERENCES users(id),
    idea_id   UUID NOT NULL REFERENCES ideas(id),
    is_owner  BOOLEAN DEFAULT false,  -- 自己产生=true，收集=false
    added_at  TIMESTAMPTZ DEFAULT now(),
    last_touch_at TIMESTAMPTZ DEFAULT now(),  -- 用于自然淡出
    PRIMARY KEY (user_id, idea_id)
);

-- 今日一点题目表
CREATE TABLE spark_questions (
    id         SERIAL PRIMARY KEY,
    question   TEXT NOT NULL,
    q_type     VARCHAR(20),  -- random_word/analogy/constraint/reverse
    active_date DATE UNIQUE  -- 每日一题
);

-- 索引
CREATE INDEX idx_ideas_author ON ideas(author_id);
CREATE INDEX idx_ideas_created ON ideas(created_at DESC);
CREATE INDEX idx_fork_child ON fork_relations(child_id);
CREATE INDEX idx_fork_parent ON fork_relations(parent_id);
CREATE INDEX idx_vault_user ON vault_items(user_id, last_touch_at);
```

### 递归CTE查询谱系图（2层）
```sql
-- 父节点（1层）
WITH RECURSive ancestors AS (
    SELECT * FROM fork_relations WHERE child_id = $1
)
SELECT i.*, fr.relation FROM ancestors fr
JOIN ideas i ON i.id = fr.parent_id;

-- 子节点（1层）
SELECT i.*, fr.relation FROM fork_relations fr
JOIN ideas i ON i.id = fr.child_id
WHERE fr.parent_id = $1;
```

---

## 7. AI 调用配置

### DeepSeek 客户端
```python
# backend/services/deepseek_client.py
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

async def collide_ideas(content_a: str, content_b: str):
    resp = await client.chat.completions.create(
        model="deepseek-chat",
        temperature=0.9,  # 高温度=更有创意
        messages=[{
            "role": "system",
            "content": "你是创意碰撞引擎。生成3个结合方案：实用型/跨界型/反常规型。每个≤300字。"
        }, {
            "role": "user",
            "content": f"点子A：{content_a}\n点子B：{content_b}"
        }]
    )
    return resp.choices[0].message.content

async def evolve_idea(content: str, angle: str, angle_desc: str):
    resp = await client.chat.completions.create(
        model="deepseek-chat",
        temperature=0.9,
        messages=[{
            "role": "system",
            "content": f"你是创意演化引擎。角度：{angle}（{angle_desc}）。生成3个变体：近/中/远。每个≤300字。"
        }, {
            "role": "user",
            "content": f"点子：{content}"
        }]
    )
    return resp.choices[0].message.content
```

### 成本估算
| 操作 | 单次成本 | 日限(100次) | 月成本 |
|---|---|---|---|
| 碰撞 | ~0.004元 | 0.4元 | ~12元 |
| 演化 | ~0.004元 | 0.4元 | ~12元 |
| 审核 | ~0.001元 | 0.1元 | ~3元 |
| **合计** | | | **~27元/月** |

---

## 8. 开发工作流（AI辅助最优方法）

### 8.1 首次开发流程
```
1. Trea AI 读取上下文包（TREA_CONTEXT + API_SPEC + DB_SCHEMA + TECH_CONSTRAINTS）
2. 从 "项目初始化" 开始：flutter create + 依赖安装
3. 按"页面"维度开发，每完成一个页面测试一个：
   - 先做 models/ → services/ → providers/
   - 再做 widgets/ → pages/
   - 最后做后端 routers/
4. 核心优先级：
   P0: circle_canvas.dart（圆圈渲染）→ home_page（主页）
   P1: detail_page（详情+谱系图）→ fork_page（Fork引导）
   P2: vault_page（仓库）→ evolve_menu（演化菜单+震动）
   P3: spark_page（今日一点）→ profile_page（个人主页）
   P4: create_page/notice_page/settings_page
```

### 8.2 给 Trea AI 的 prompt 模板

**开发新页面：**
```
请阅读 TREA_CONTEXT.md 和 TECH_CONSTRAINTS.md。
现在开发 [页面名]，功能要求：
1. [功能点1]
2. [功能点2]
约束：
- 圆圈用 CustomPainter 渲染，颜色从 COLOR_POOL 真随机
- 震动用 Haptics.step()
- 字数限制300字
请先生成完整代码，包含widget + provider + API调用。
```

**开发后端API：**
```
请阅读 API_SPEC.md 和 DB_SCHEMA.md。
开发 [API端点名]，要求：
1. 请求/响应格式严格按 API_SPEC.md
2. 数据库查询按 DB_SCHEMA.md
3. 异步处理（async/await）
4. AI调用用 deepseek_client.py
```

### 8.3 调试技巧
- 圆圈布局调试：先固定随机种子（`Random(42)`），调好布局后再改回真随机
- 震动调试：iOS模拟器不支持震动，用`print('haptic: step')`替代
- 后端调试：`uvicorn main:app --reload`
- 谱系图调试：用PyMuPDF导出SQL查询结果可视化

---

## 9. 开发阶段划分

### Phase 1: MVP（4周）
| 周 | 交付物 |
|---|---|
| W1 | 项目搭建 + 数据库 + 基础API + 圆圈渲染组件 |
| W2 | 主页 + 点子详情 + Fork引导 + 发布点子 |
| W3 | 仓库 + 演化菜单（碰撞+演化） + 震动反馈 |
| W4 | 今日一点 + 个人主页 + 通知 + 设置 + 联调 |

### Phase 2: 社群测试版（2周）
- AI审核上线
- 冷启动PGC内容池填充（500-1000条）
- Bug修复 + 性能优化
- 交付用户社群测试

### Phase 3: 迭代（根据反馈）
- 成本模型 + 次数限制
- 暗色模式优化
- 完整谱系树
- 私密选项

---

## 10. 验收标准

- [ ] 9个页面全部可交互
- [ ] 圆圈渲染60fps（CustomPainter性能达标）
- [ ] 震动反馈在iOS/Android真机上正常触发
- [ ] 碰撞/演化AI生成3方案，用户可选1采纳
- [ ] Fork关系正确建立，谱系图2层正确显示
- [ ] 自然淡出：7天未触碰→变小→移出仓库
- [ ] 今日一点：3分钟倒计时+草稿23:59过期+不可补做
- [ ] AI审核：先发后审，违规撤回
- [ ] 后端API全部通过自动化测试
