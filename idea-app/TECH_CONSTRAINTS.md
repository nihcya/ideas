# TECH_CONSTRAINTS.md — 点子 App 技术约束

> 供 Trea IDE / Codex / WorkBuddy 读取  
> 技术栈：Flutter 3.24+ / FastAPI / PostgreSQL 16 / Redis 7 / DeepSeek  
> 本文档列出所有技术约束，AI生成代码时必须遵守

---

## 1. 前端约束（Flutter）

### 1.1 圆圈渲染

- **使用 CustomPainter + CustomPaint**，不用GridView/ListView
- 圆圈位置用**真随机算法**分配（非网格排列），避免重叠超过30%
- 最小圆圈直径 **60pt**（触控命中率），最大 **120pt**
- 滚动加载：**伪随机延展算法**（向下滚动时，在可视区域下方继续生成随机圆圈）
- 圆圈**不显示任何文字**（方案C，强制随机激发）
- 圆圈颜色从**后端返回的color_hex**渲染，前端不做颜色分配

```dart
// 圆圈渲染模板
class CircleCanvas extends CustomPainter {
  final List<CircleData> circles;
  @override
  void paint(Canvas canvas, Size size) {
    for (final c in circles) {
      final paint = Paint()..color = Color(int.parse('0xFF${c.colorHex.substring(1)}'));
      // 金边圆圈
      if (c.borderStyle == 'gold-thin') {
        canvas.drawCircle(c.center, c.radius, paint);
        canvas.drawCircle(c.center, c.radius, Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3
          ..color = Color(0xFFFFD700));
      } else {
        canvas.drawCircle(c.center, c.radius, paint);
      }
    }
  }
}
```

### 1.2 色彩系统

- 15色池由**后端管理**，前端只渲染后端返回的color_hex
- **禁止**前端按内容/类型分配颜色（会导致同色=同类的伪分类）
- 暗色模式：色系专门设计一套暗色版本（降低饱和度+提高亮度），后期实现
- 色盲用户：颜色不承载语义，无需特殊处理

### 1.3 圆圈动效

- **浮动动效**：圆圈轻微上下浮动（±5px，3秒周期，不同圆圈delay不同）
- **悬停放大**：用户长按/悬停时圆圈放大1.1倍+柔光阴影
- **Fork涟漪**：被fork瞬间圆圈扩散涟漪（半径1.5倍，淡出）
- **淡出动效**：status=fading时圆圈逐帧变小变透明；status=faded时完全不显示
- 用 **AnimationController + Tween** 实现，60fps

```dart
// 浮动动效模板
class FloatingCircle extends StatefulWidget {
  @override
  State createState() => _FloatingCircleState();
}
class _FloatingCircleState extends State<FloatingCircle>
    with TickerProviderStateMixin {
  late AnimationController _controller;
  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: Duration(seconds: 3),
      vsync: this,
    )..repeat(reverse: true);
  }
  @override
  void dispose() { _controller.dispose(); super.dispose(); }
}
```

### 1.4 震动反馈

- **演化菜单**：点击选项时触发 `HapticFeedback.mediumImpact()`
- **圆圈点击**：触发 `HapticFeedback.selectionClick()`
- **Fork成功**：触发 `HapticFeedback.heavyImpact()`
- **演化菜单漫步动效**：每个选项之间的路径有步行动画，每步触发 `HapticFeedback.lightImpact()`
- iOS: 使用Taptic Engine（通过HapticFeedback class）
- Android: 使用振动器（通过HapticFeedback class）

```dart
import 'package:flutter/services.dart';

// 演化菜单点击
void _onEvolveMenuTap(String action) {
  HapticFeedback.mediumImpact();
  switch (action) {
    case 'collide': _navigateToCollide();
    case 'evolve':  _navigateToEvolve();
  }
}
```

### 1.5 状态管理

- **使用 Riverpod 2.x**（类型安全，测试友好）
- 核心Provider：
  - `authProvider` — 用户认证状态
  - `exploreProvider` — 主页圆圈列表
  - `vaultProvider` — 仓库圆圈列表
  - `sparkProvider` — 今日一点状态
  - `ideaDetailProvider` — 当前查看的点子详情
  - `notificationsProvider` — 通知列表

```dart
// Riverpod 模板
final exploreProvider = FutureProvider.family<List<CircleData>, int>((ref, offset) async {
  final api = ref.read(apiProvider);
  return api.getExplore(limit: 25, offset: offset);
});
```

### 1.6 网络层

- 使用 **dio** HTTP客户端（拦截器+错误处理）
- JWT Token 存储在 **flutter_secure_storage**
- 请求拦截器自动添加 `Authorization: Bearer {token}`
- 响应拦截器统一处理401（跳转登录）

```dart
// Dio 配置模板
final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8000/api'));
  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) async {
      final storage = const FlutterSecureStorage();
      final token = await storage.read(key: 'jwt_token');
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
      handler.next(options);
    },
    onError: (e, handler) {
      if (e.response?.statusCode == 401) {
        // 跳转登录
      }
      handler.next(e);
    },
  ));
  return dio;
});
```

### 1.7 字数限制

- 所有点子输入框 **maxLength: 300**
- 显示字数计数器（`X/300`）
- 超过300字时禁止继续输入

### 1.8 页面导航

- 使用 **go_router** 声明式路由
- 底部Tab：探索/仓库/一点/我（4个主页面）
- 详情页等使用 push 跳转（保留返回）

---

## 2. 后端约束（FastAPI）

### 2.1 API规范

- 所有端点前缀 `/api`
- 所有请求/响应均为JSON
- 使用 **Pydantic v2** 模型做请求/响应验证
- 响应统一用对应的ResponseModel
- 错误统一格式：`{ "error": { "code": "...", "message": "..." } }`

```python
# Pydantic 模型模板
from pydantic import BaseModel, Field

class IdeaCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=300)

class IdeaResponse(BaseModel):
    id: str
    content: str
    color_hex: str
    source: str
    border_style: str
    created_at: datetime

# 路由模板
@router.post("/ideas", response_model=IdeaResponse, status_code=201)
async def create_idea(req: IdeaCreate, user: User = Depends(get_current_user)):
    # 1. 审核
    audit_result = await audit_content(req.content)
    if not audit_result.pass_:
        raise HTTPException(403, detail={"error": {"code": "AUDIT_FAILED", "message": audit_result.reason}})
    # 2. 随机分配颜色
    color_hex = random.choice(COLOR_POOL)
    # 3. 写入
    idea = await Idea.create(content=req.content, color_hex=color_hex, ...)
    return IdeaResponse(...)
```

### 2.2 数据库ORM

- 使用 **SQLAlchemy 2.0（async）**
- 异步引擎：`create_async_engine("postgresql+asyncpg://...")`
- Session：`async_sessionmaker`
- 查询用 **select() + where()** 风格（不用legacy query API）

```python
# SQLAlchemy async 模板
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/dianzi_app")
async_session = async_sessionmaker(engine, class_=AsyncSession)

class Base(DeclarativeBase): pass

class Idea(Base):
    __tablename__ = "ideas"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=gen_random_uuid)
    content: Mapped[str] = mapped_column(String(300))
    # ...
```

### 2.3 AI调用（DeepSeek）

- 使用 **openai** SDK（兼容模式，base_url指向DeepSeek）
- 碰撞/演化：temperature=0.9（高温度=更有创意）
- 审核：temperature=0.1（低温度=严格判断）
- 超时：30秒
- 重试：2次（间隔3秒）
- 返回JSON格式，需解析

```python
# DeepSeek 客户端模板
from openai import AsyncOpenAI

deepseek = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

async def call_collide_ai(content_a: str, content_b: str) -> dict:
    prompt = COLLIDE_PROMPT.format(content_a=content_a, content_b=content_b)
    resp = await deepseek.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)
```

### 2.4 审核机制

- **先发后审**：点子先入库，AI异步审核，不阻塞用户
- 审核流程：发布 → 入库 → AI审核 → 不通过则标记status='rejected'并通知作者
- 审核维度：违禁词（精确匹配） + AI语义审核
- 违禁词库：维护在数据库表中，可动态更新

```python
# 审核流程模板
async def audit_content(content: str) -> AuditResult:
    # 1. 违禁词精确匹配（快速）
    if contains_banned_word(content):
        return AuditResult(pass_=False, reason="包含违禁词")
    # 2. AI语义审核
    result = await call_audit_ai(content)
    return AuditResult(pass_=result["pass"], reason=result.get("reason", ""))
```

### 2.5 定时任务

- 使用 **APScheduler** 或 **FastAPI BackgroundTasks**
- 每日任务：
  - 00:00 — 更新今日一点题目
  - 00:00 — 清理过期草稿（expires_at < NOW()）
  - 01:00 — 自然淡出检查（更新status=fading/faded）
  - 02:00 — 热门缓存刷新（近30天fork数Top重新计算）

```python
# APScheduler 模板
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=0, minute=0)
async def update_spark_question():
    # 更新今日一点
    ...

@scheduler.scheduled_job("cron", hour=1, minute=0)
async def natural_fade_check():
    # 自然淡出检查
    await db.execute(text("""
        UPDATE ideas SET status = 'fading'
        WHERE id IN (
            SELECT i.id FROM vault_items vi
            JOIN ideas i ON i.id = vi.idea_id
            WHERE i.status = 'active'
              AND vi.last_touch_at < NOW() - INTERVAL '7 days'
        )
    """))
    # 移出仓库（8天未触碰）
    await db.execute(text("""
        DELETE FROM vault_items
        WHERE last_touch_at < NOW() - INTERVAL '8 days'
    """))
```

### 2.6 Redis缓存

- 使用 **redis.asyncio** 异步客户端
- 缓存key规范见 DB_SCHEMA.md 第13节
- 缓存失效策略：
  - 点子被fork → 删除 `idea:detail:{id}` 缓存
  - 仓库变化 → 删除 `user:vault:{user_id}` 缓存
  - 新通知 → 删除 `notifications:unread:{user_id}` 缓存

---

## 3. 通用约束

### 3.1 内容约束

- 点子文本 **≤300字**（前后端双重验证）
- 用户名 **3-20字符**
- 用户简介 **≤50字**
- 通知文案 **≤200字**

### 3.2 颜色分配

- **后端唯一分配**，前端不参与颜色逻辑
- 从COLOR_POOL（15色）中 `random.choice()` 分配
- **禁止**按内容哈希分配（会导致同色=同类的伪分类）
- 颜色一旦分配，**不可更改**（点子生命周期内固定）

### 3.3 Fork关系

- Fork时**自动建立**fork_relations记录，用户无感知
- 碰撞产生的新点子有**2个父节点**（merge关系）
- 演化产生的新点子有**1个父节点**（evolve关系）+ evolved_from字段记录角度
- Fork关系**不可删除**（永久记录，谱系图完整性）

### 3.4 仓库移出规则

- **7天未触碰** → status变为 'fading'（圆圈变小变淡）
- **8天未触碰** → 从vault_items移出（圆圈消失）
- 移出后：
  - 如果点子**被fork过** → ideas表保留（谱系图需要）
  - 如果点子**未被fork过** → ideas表物理删除

### 3.5 今日一点规则

- 每日0:00更新题目
- 3分钟倒计时
- 倒计时结束**自动保存草稿**，可继续写
- 草稿**当日23:59过期**，第二天清空
- **不可补做**往期题目
- 每人每日**只能提交一次**

### 3.6 热度算法

- **唯一指标**：fork_count（被fork总数）
- 主页圆圈大小 = `f(fork_count, 近期衰减)`
- **不引入**浏览量、点赞数、停留时长等任何其他指标
- 主页构成：90%随机 + 10%近30天fork数Top
- **禁止**个性化推荐算法

### 3.7 搜索

- **不做搜索功能**
- 谱系图导航**不算搜索**（沿fork关系走）
- 禁止后期加搜索框

### 3.8 内容分类

- **不加type**（预设分类）
- **不加tag**（自由标签）
- 点子回归到纯粹元素：文本 + 作者 + fork关系

---

## 4. 安全约束

- 密码用 **bcrypt** 哈希，cost=12
- JWT Token 有效期7天，刷新机制可选
- SQL注入防护：SQLAlchemy参数化查询，禁止拼接SQL
- XSS防护：前端渲染时自动转义
- CSRF防护：SameSite Cookie + Authorization Header
- 速率限制：碰撞/演化API每用户每日上限（MVP不限制，后期用Redis计数器实现）

---

## 5. 性能约束

| 指标 | 目标 | 说明 |
|---|---|---|
| 主页加载 | <1s | 首屏25个圆圈渲染 |
| 圆圈渲染 | 60fps | CustomPainter优化 |
| API响应 | <200ms | 不含AI调用的端点 |
| AI碰撞/演化 | <5s | DeepSeek响应时间 |
| AI审核 | <2s | 异步不阻塞用户 |
| 数据库查询 | <50ms | 核心查询走索引 |

---

## 6. 目录结构（最终版）

```
idea-app/
├── PRD/点子App_PRD_V1.0.pdf
├── TREA_CONTEXT.md          # 主配置
├── API_SPEC.md              # API规格
├── DB_SCHEMA.md             # 数据库DDL
├── TECH_CONSTRAINTS.md      # 本文件
├── DISCUSSION_NOTES.md      # 讨论纪要
├── prototype/index.html     # 低保真原型
├── frontend/                # Flutter项目
│   ├── pubspec.yaml
│   └── lib/
│       ├── main.dart
│       ├── app.dart
│       ├── routers/
│       ├── providers/       # Riverpod
│       ├── models/
│       ├── services/        # API调用
│       ├── widgets/
│       │   ├── circle_canvas.dart
│       │   ├── circle_painter.dart
│       │   ├── evolve_menu.dart
│       │   └── lineage_tree.dart
│       └── screens/
│           ├── explore_screen.dart
│           ├── vault_screen.dart
│           ├── spark_screen.dart
│           ├── idea_detail_screen.dart
│           ├── profile_screen.dart
│           ├── create_idea_screen.dart
│           ├── fork_guide_screen.dart
│           ├── notifications_screen.dart
│           └── settings_screen.dart
└── backend/                 # FastAPI项目
    ├── requirements.txt
    ├── main.py
    ├── config.py
    ├── database.py
    ├── models/              # SQLAlchemy
    ├── schemas/             # Pydantic
    ├── routers/             # API路由
    ├── services/            # 业务逻辑
    │   ├── deepseek_client.py
    │   ├── audit_service.py
    │   └── fade_service.py
    ├── prompts/             # AI提示词
    └── tests/
```

---

## 7. Trea AI 开发指令模板

### 7.1 生成Flutter页面
```
请阅读 TREA_CONTEXT.md + TECH_CONSTRAINTS.md + API_SPEC.md。
开发 [页面名]（如 explore_screen.dart），要求：
1. 使用 Riverpod 状态管理
2. 使用 CustomPainter 渲染圆圈（不用GridView）
3. 圆圈颜色从API返回的color_hex渲染
4. 金边圆圈用 PaintingStyle.stroke + Color(0xFFFFD700)
5. 点击圆圈触发 HapticFeedback.selectionClick() + 跳转详情页
6. 圆圈浮动动效（AnimationController, 3秒周期）
7. 底部Tab栏用 go_router
```

### 7.2 生成后端API
```
请阅读 API_SPEC.md + DB_SCHEMA.md + TECH_CONSTRAINTS.md。
开发 [API端点名]，要求：
1. 请求/响应严格按 API_SPEC.md
2. 使用 SQLAlchemy 2.0 async + Pydantic v2
3. 认证依赖注入 get_current_user
4. AI调用用 deepseek_client.py
5. 审核流程：先发后审（不阻塞用户）
6. 颜色分配：random.choice(COLOR_POOL)
7. Fork关系自动建立
```

### 7.3 生成数据库查询
```
请阅读 DB_SCHEMA.md。
开发 [查询名]，要求：
1. 使用 SQLAlchemy 2.0 select() + where() 风格
2. 走索引（检查DB_SCHEMA.md中的索引定义）
3. 异步执行（async/await）
4. 返回Pydantic模型
```
