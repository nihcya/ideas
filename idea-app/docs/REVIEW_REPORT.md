# 代码审查报告 - idea-app

**审查日期**：2026-07-29
**审查范围**：全量代码 + 阶段6主题重构专项
**审查者**：Code Reviewer（标准团队）
**项目版本**：0.1.0（commit `c441bb6` 之后）

---

## 一、整体印象

idea-app 是一个设计完成度较高的「创意激发社区」应用，后端 FastAPI + SQLAlchemy + PostgreSQL/SQLite 的工程实践整体优秀——并发安全（fork_count 原子自增）、缓存击穿防护（互斥锁 + 短轮询）、scheduler 多 worker 防重（PG advisory lock）、生产环境拒绝 SQLite 静默降级，这些都是少见的工程严谨度，并且都有配套测试证明修复有效。前端 Flutter Web 用 Riverpod + go_router + AppColors ThemeExtension 的架构清晰，API 基础 URL 通过 `--dart-define=API_BASE_URL=...` 编译时注入，部署多环境支持做得规范。

但本次审查发现 **4 个 Blocker 级问题**，集中在安全侧：注册接口未限流（REGISTER_LIMIT 定义了却没应用）、用户自填 LLM API URL 存在 SSRF 风险（仅校验协议前缀，未拦截内网地址）、用户 API Key 明文入库、AI 调用失败时异常细节直接回传客户端（绕过 main.py 全局 500 处理器）。这些问题组合起来会让攻击者通过设置页发起内网请求并泄露内部信息。

主题重构（阶段6）整体落地不错，AppColors 的 `lerp`/`copyWith`/`forBrightness` 实现规范，但仍有 6 处硬编码颜色残留在 `idea_detail_screen.dart` 和 `evolve_menu.dart`（碰撞/演化按钮的蓝紫和绿青色系），未纳入语义色板。另外 `dark_mode` 设置字段在前后端都已建模，但 `app.dart` 硬编码 `ThemeMode.dark`，导致该设置完全是死代码。

---

## 二、🔴 Blocker（必须修复）

### B1. 注册接口缺失速率限制（REGISTER_LIMIT 定义了却未应用）

- **文件**：`backend/routers/auth.py:29-30`、`backend/services/rate_limit.py:10`
- **问题**：
  ```python
  # rate_limit.py 定义了 REGISTER_LIMIT
  REGISTER_LIMIT = "5/minute"        # 注册：每分钟 5 次

  # auth.py 的 register 函数却没有装饰器，也没有 Request 参数
  @router.post("/register", response_model=AuthResponse, status_code=201)
  async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
      ...
  ```
  对比同文件的 `login`（line 52-54）正确应用了 `@limiter.limit(LOGIN_LIMIT)` 并声明了 `request: Request` 参数。
- **影响**：攻击者可无限调用 `/api/auth/register`，导致：
  - DB 写入洪水（每个请求都会 bcrypt hash，CPU 密集）
  - 用户名枚举（通过 400 ALREADY_EXISTS 响应探测已存在用户名）
  - 拒绝服务（bcrypt rounds=12 单次约 200ms，并发可打满 worker）
- **修复建议**：
  ```python
  @router.post("/register", response_model=AuthResponse, status_code=201)
  @limiter.limit(REGISTER_LIMIT)
  async def register(request: Request, req: RegisterRequest, db: AsyncSession = Depends(get_db)):
      ...
  ```
  注意 slowapi 要求被装饰函数的第一个参数必须是 `request: Request`。

### B2. SSRF 漏洞：用户自填 LLM API URL 未做内网地址拦截

- **文件**：`backend/schemas/settings.py:49-57`、`backend/services/deepseek_client.py:47-49`
- **问题**：`SettingsUpdateRequest.validate_url` 仅校验 `http://`/`https://` 前缀，未拦截内网/元数据地址：
  ```python
  @field_validator("llm_api_url")
  @classmethod
  def validate_url(cls, v: str | None) -> str | None:
      if v is None or v == "":
          return v
      v = v.strip()
      if not (v.startswith("http://") or v.startswith("https://")):
          raise ValueError("API 地址必须以 http:// 或 https:// 开头")
      return v   # ← 没有任何内网地址拦截
  ```
  随后 `deepseek_client._get_client` 直接 `AsyncOpenAI(base_url=user_url)`，会对用户指定的 URL 发起 HTTP 请求。
- **影响**：
  - 攻击者设置 `llm_api_url=http://169.254.169.254/latest/meta-data/iam/security-credentials/` 可窃取云主机 IAM 凭证
  - 设置 `llm_api_url=http://127.0.0.1:8000/health` 可探测内网服务端口
  - 设置 `llm_api_url=http://postgres:5432` 可探测容器内网域名
  - 配合 B3（异常细节回传），响应内容会通过 `f"AI 调用失败: {e}"` 泄露给攻击者
- **修复建议**：在 `validate_url` 中增加：
  1. 解析 URL 的 host
  2. 解析 IP，拒绝私有/保留地址段（`127.0.0.0/8`、`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`169.254.0.0/16`、`::1`、`fc00::/7`）
  3. 拒绝非标准端口（可选）
  4. 拒绝以 `localhost`、`postgres`、`redis` 等容器内部域名（白名单更稳）
  5. 解析 DNS 后再次校验 IP（防 DNS rebinding）

### B3. AI 调用异常细节直接回传客户端

- **文件**：`backend/routers/evolve.py:55`、`backend/routers/evolve.py:159`
- **问题**：
  ```python
  except Exception as e:
      raise HTTPException(
          status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
          detail={"error": {"code": "INTERNAL_ERROR", "message": f"AI 调用失败: {e}"}},
      )
  ```
  `main.py:241-251` 的全局异常处理器在 prod 环境会隐藏内部错误，但**显式 raise HTTPException 会绕过全局处理器**，导致 `e` 的内容（可能包含内部 URL、连接拒绝信息、API Key 是否存在的迹象）直接返回给客户端。
- **影响**：与 B2 组合形成完整 SSRF 利用链——攻击者发送恶意 `llm_api_url`，通过错误响应反查内网服务信息。单独看也会泄露：DeepSeek 服务返回的 4xx 错误体、内部连接超时细节、堆栈中的主机名等。
- **修复建议**：
  ```python
  except Exception as e:
      import logging
      logging.exception("AI collide call failed")  # 服务端完整记录
      raise HTTPException(
          status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
          detail={"error": {"code": "AI_UNAVAILABLE", "message": "AI 服务暂时不可用，请稍后再试"}},
      )
  ```
  统一返回脱敏的 503，原始异常走日志。

### B4. 用户 API Key 明文存储

- **文件**：`backend/routers/settings.py:44`、`backend/models/user.py:22`
- **问题**：
  ```python
  # settings.py
  if req.llm_api_key is not None:
      user.llm_api_key = req.llm_api_key.strip()   # ← 明文入库

  # user.py
  llm_api_key: Mapped[str] = mapped_column(String(255), default="", server_default="")
  ```
  `_mask_api_key` 仅在读取时脱敏显示，但数据库存储的是用户原始 Key。
- **影响**：数据库泄露场景（备份外泄、SQL 注入、运维误操作）下，所有配置过 LLM Key 的用户的 DeepSeek/OpenAI 账户凭证直接暴露，可被转卖或盗刷。LLM API Key 通常关联着付费账户，损失可量化。
- **修复建议**：
  1. 引入对称加密（如 `cryptography.fernet.Fernet`），密钥从环境变量 `LLM_KEY_ENCRYPTION_KEY` 读取
  2. 写入时加密：`user.llm_api_key = encrypt(req.llm_api_key.strip())`
  3. 读取时解密后再传给 `_get_client`（`settings.py` 的 `get_settings` 仍返回 mask 后的版本给前端）
  4. 密钥不进 `.env.example`，仅在生产环境注入

---

## 三、🟡 Suggestion（建议修复）

### S1. 主题重构残留硬编码颜色

- **文件**：
  - `frontend/lib/screens/idea_detail_screen.dart:135` `Color(0xFF6C5CE7)`（碰撞按钮）
  - `frontend/lib/screens/idea_detail_screen.dart:141` `Color(0xFF00B894)`（演化按钮）
  - `frontend/lib/widgets/evolve_menu.dart:175,176,209,220` 4 处渐变色
- **问题**：阶段6 AppColors 重构目标是用 ThemeExtension 替换散落的 `Color(0xFFxxxxxx)`，但碰撞/演化按钮的蓝紫和绿青色系未纳入 `AppColors`，在两个文件中重复硬编码。如果未来要做暗色/亮色差异化或品牌色调整，需要多处修改。
- **改进建议**：在 `AppColors` 增加两个语义色：
  ```dart
  final Color collideAccent;  // 碰撞按钮主色（蓝紫）
  final Color evolveAccent;   // 演化按钮主色（绿青）
  ```
  在 `idea_detail_screen.dart` 和 `evolve_menu.dart` 中通过 `AppColors.of(context).collideAccent` 读取。渐变第二色可派生或一并纳入。

### S2. `dark_mode` 设置为死代码

- **文件**：`frontend/lib/app.dart:18`、`backend/models/user.py:17`、`frontend/lib/services/settings_service.dart:7,16,27,55,63`
- **问题**：
  - 后端 User 模型有 `dark_mode` 字段，settings 接口可读写
  - 前端 `SettingsService` 也定义了 `darkMode` 字段并参与序列化
  - 但 `app.dart` 写死 `themeMode: ThemeMode.dark`，从不读取该设置
  - 用户在设置页切换「暗色模式」无任何效果
- **改进建议**：要么在 `DianziApp` 中 `ref.watch` 一个 themeModeProvider，根据用户设置切换 `ThemeMode.dark`/`ThemeMode.light`；要么明确删除该字段（如果产品定位就是纯暗色）。当前状态会误导用户。

### S3. `CountdownRingPainter.shouldRepaint` 漏判字段

- **文件**：`frontend/lib/widgets/countdown_ring_painter.dart:61-63`
- **问题**：
  ```dart
  @override
  bool shouldRepaint(covariant CountdownRingPainter oldDelegate) {
    return progress != oldDelegate.progress || color != oldDelegate.color;
    // ← 漏了 backgroundColor 和 strokeWidth
  }
  ```
  如果父组件改了 `backgroundColor` 或 `strokeWidth`，CustomPaint 不会重绘，导致显示旧值。
- **改进建议**：
  ```dart
  return progress != oldDelegate.progress ||
      color != oldDelegate.color ||
      backgroundColor != oldDelegate.backgroundColor ||
      strokeWidth != oldDelegate.strokeWidth;
  ```

### S4. `notifications.py` 使用 `__import__("uuid")` 反模式

- **文件**：`backend/routers/notifications.py:67`
- **问题**：
  ```python
  ids.append(__import__("uuid").UUID(nid))
  ```
  `uuid` 在 `deps.py`、`routers/ideas.py`、`routers/evolve.py` 等处都已正常 `import uuid`，此处用 `__import__` 是无理由的特立独行，可读性差且每次调用都走 import 机制（虽然有缓存）。
- **改进建议**：文件顶部 `import uuid`，此处改为 `uuid.UUID(nid)`。

### S5. `get_user_profile` 未鉴权，存在用户信息枚举风险

- **文件**：`backend/routers/users.py:16-27`
- **问题**：`GET /api/users/{user_id}` 没有 `Depends(get_current_user)`，任何人持有 UUID 即可读取该用户的：用户名、bio、produced/collected/forked 统计、全部点子圆圈。UUID 虽不可枚举，但可通过通知接口的 `actor_id`、点子详情的 `author.id` 间接获得，进而拼出用户行为画像。
- **改进建议**：如果是公开主页（产品上是合理的），保留无鉴权但增加速率限制 `@limiter.limit("30/minute")`；如果应限本人/好友，加 `Depends(get_current_user)` 并校验关系。当前最少应该加限流。

### S6. 测试覆盖严重不足

- **文件**：`backend/tests/`（仅 `conftest.py`、`test_concurrency.py`、`test_spark_ai.py`）
- **问题**：
  - 无 auth 注册/登录/JWT 验证测试（B1 的限流缺失正是因为没测试覆盖才发现）
  - 无 ideas/vault/notifications/settings 路由级测试
  - 无 FastAPI TestClient 端到端测试
  - 无 Pydantic schema 校验测试（如 SSRF 校验、字段长度边界）
- **改进建议**：补充至少以下场景的测试：
  1. 注册：用户名重复、密码长度边界、用户名格式校验
  2. 登录：错误密码、不存在用户、token 过期
  3. JWT：无 token、错误 token、过期 token、伪造 token
  4. 限流：注册/登录/AI 接口超限返回 429
  5. 设置：`llm_api_url` 拒绝内网地址（B2 的回归测试）
  6. 关键业务：Fork 父点子不存在、Fork 自己、演化 6 角度参数校验

### S7. `get_idea_detail` 5 次串行 DB 查询

- **文件**：`backend/routers/ideas.py:146-234`
- **问题**：单次详情请求执行 5 次 await DB 查询（idea → author → vault_item → parents → children），每次都引入一次网络往返。非 N+1（无循环），但延迟叠加。
- **改进建议**：可用 `selectinload`/`joinedload` 关系加载，或合并 parents/children 为一次 UNION 查询。当前 PG 单次往返约 1-2ms，5 次约 10ms，MVP 阶段可接受，但流量上来后建议优化。

### S8. Web 平台 JWT 存于 localStorage（XSS 风险）

- **文件**：`frontend/lib/services/web_storage.dart:1-19`、`frontend/lib/services/storage_service.dart:11-17`
- **问题**：Web 环境下 JWT 直接写入 `window.localStorage`，明文且可被任意 JS 读取。一旦发生 XSS（如未来引入第三方组件、用户内容渲染漏洞），攻击者可一键窃取所有登录用户 token。
- **改进建议**：
  - 短期：在 `web_storage.dart` 顶部明确注释「XSS 风险已知，需配合严格 CSP」
  - 中期：改用 `httpOnly` Cookie 传输 token，后端开启 `SameSite=Strict`
  - 长期：HTTPS 部署后切回 `FlutterSecureStorage`（依赖 SubtleCrypto）
  - 已在代码注释中说明该限制，属已知问题，但应在部署文档强调 CSP 配置

---

## 四、💭 Nit（可改进）

### N1. `_mask_api_key` 边界判断偏保守

- **文件**：`backend/schemas/settings.py:11`
- **问题**：`if len(key) <= 8` 用 `<=` 而非 `<`，对于长度 8 的 key 会全部掩码（实际 `key[:3] + '*'*1 + key[-4:]` 即可保留 3+4 显示）。
- **改进建议**：改为 `if len(key) < 8`。无安全影响，仅显示更友好。

### N2. `EvolveMenu` 提供两种等价调用方式

- **文件**：`frontend/lib/widgets/evolve_menu.dart:9-20`（`showEvolveMenu` 顶级函数）vs `42-53`（`EvolveMenu.show` 静态方法）
- **问题**：两个 API 做完全相同的事，调用方会困惑选哪个。
- **改进建议**：保留一个（推荐保留顶级函数 `showEvolveMenu`，更符合 Dart 惯例），删除另一个或标 `@Deprecated`。

### N3. `_seed_initial_data` 内联大量种子数据

- **文件**：`backend/database.py:106-227`
- **问题**：30 条 PGC 点子 + 30 条 spark 题目 + 14 条违禁词全部以 Python list 内联在函数体中，函数长度 120+ 行。项目根目录已有 `backend/db/seed.sql`，但未使用。
- **改进建议**：将 PGC 数据迁移到 `db/seed.sql` 或 `db/seed.json`，函数读取文件加载，便于运营人员维护内容而不改代码。

### N4. `SCHEDULER_LOCK_KEY` 字面量写法

- **文件**：`backend/main.py:27`
- **问题**：`SCHEDULER_LOCK_KEY = 0x_D1A2_3BEF` 在 `0x` 后立即用下划线，Python 3.6+ 合法但不常见，常规写法是 `0xD1A2_3BEF`。
- **改进建议**：调整为 `0xD1A2_3BEF`。

### N5. `notifications.py` 的 `marked` 变量类型回退

- **文件**：`backend/routers/notifications.py:81`
- **问题**：`marked = result.rowcount if hasattr(result, "rowcount") else 0` 用 `hasattr` 兜底，但 SQLAlchemy 的 `Result` 对象一定有 `rowcount`，这里的兜底是死代码。
- **改进建议**：直接 `marked = result.rowcount or 0`，删除 `hasattr` 判断。

### N6. `auth.py` 的 register 接口未返回 `dark_mode`/`forkable` 默认值

- **文件**：`backend/routers/auth.py:48-49`
- **问题**：注册响应只返回 `user_id`/`username`/`token`，前端首次进入需要再调一次 `/api/settings` 拉默认值。
- **改进建议**：可在 `AuthResponse` 中可选返回 `settings` 嵌套对象，减少一次往返。低优先级。

---

## 五、✨ 值得赞美的代码

### 1. fork_count 原子自增 + 对照测试
`backend/routers/ideas.py:359-369` 用 `Idea.fork_count + 1` 的 SQL UPDATE 而非 ORM 读-改-写，正确避免并发丢失更新。`test_concurrency.py:55-138` 还提供了「正确写法」和「错误写法」的对照测试，用 50 并发证明修复有效——这种「用测试证明 bug 存在与否」的工程素养非常少见。

### 2. 缓存击穿互斥锁
`backend/routers/ideas.py:62-72, 136-139` 实现了完整的 cache stampede 防护：抢锁失败者短轮询等待缓存，锁持有者崩溃时降级查库，避免请求无限阻塞。`test_concurrency.py:300-363` 用 10 并发验证 DB 查询次数 ≤ 2，工程质量极高。

### 3. PG advisory lock 防 scheduler 多 worker 重复执行
`backend/main.py:49-66` 用 `pg_try_advisory_lock` 让多 worker 环境下仅一个 worker 执行定时任务，SQLite 自动跳过（单写入者无并发问题），并通过环境变量 `DIANZI_SCHEDULER_ENABLED` 显式控制 prod 启用——比常见的「靠部署文档约束单 worker」稳健得多。

### 4. 生产环境拒绝 SQLite 静默降级
`backend/database.py:66-71` 在 `APP_ENV=prod` 且 PG 不可用时直接 `raise RuntimeError`，而不是悄悄切到 SQLite。配合测试 `test_concurrency.py:253-265`，避免了一个常见线上事故：开发用 SQLite 跑得好好的，生产切 PG 失败后静默降级导致并发写锁死。

### 5. AppColors ThemeExtension 设计规范
`frontend/lib/theme/app_theme.dart:134-262` 的 `AppColors` 实现了完整的 `lerp`（主题切换动画）、`copyWith`（不可变更新）、`forBrightness`（明暗工厂），文档注释清晰说明每个色的用途。`AppColors.of(context)` 提供安全 fallback。这是 Flutter 主题扩展的标准范例。

### 6. API 基础 URL 编译时注入
`frontend/lib/services/api_client.dart:13-16` 用 `String.fromEnvironment('API_BASE_URL', ...)` + `--dart-define` 实现多环境切换，无运行时配置文件加载，无硬编码 URL，前端 `lib/` 全文搜索 `/api/` 零命中——部署规范度满分。

### 7. 统一错误响应格式 + 前端多格式兼容
后端 `main.py:241-251` 统一 500 返回 `{error: {code, message}}`，前端 `api_client.dart:65-165` 兼容了 4 种 FastAPI 错误格式（直接 error、detail 包装、Pydantic 数组、字符串 detail），并提取 Pydantic 字段名拼接错误消息，用户体验一致。

### 8. Pydantic 字段约束到位
所有 schema 对关键字段都设置了 `min_length`/`max_length`/`pattern`/`ge`/`le`：用户名 regex 限制、密码长度、点子内容 1-300 字、color_hex `^#[0-9A-Fa-f]{6}$`、size_score 0-1 区间。边界校验在入口完成。

---

## 六、主题重构专项审查

### 6.1 AppColors 设计评估 ✅

`AppColors` ThemeExtension 实现质量高：
- ✅ 11 个语义色覆盖了背景/表面/卡片/分隔线/文本主次/金色/错误/成功/Fork 强调/谱系线
- ✅ `lerp` 实现完整，支持明暗主题平滑过渡
- ✅ `copyWith` 字段完整，符合 Flutter 不可变约定
- ✅ `forBrightness` 工厂方法清晰区分明暗
- ✅ `of(context)` 提供安全 fallback `?? dark`
- ✅ 通过 `extensions: [colors]` 正确注册到 ThemeData
- ✅ 文档注释说明每个色的语义和用途

### 6.2 主题重构覆盖率 ⚠️

通过 `grep "Color(0x[0-9A-Fa-f]{8}"` 扫描 `frontend/lib/`，发现 28 处 `Color(0xFF...)`：
- ✅ 22 处在 `app_theme.dart` 内部（AppColors 的 dark/light 定义）—— 合理
- ⚠️ 6 处散落在业务代码中—— 重构未完成：

| 文件 | 行号 | 颜色 | 用途 |
|------|------|------|------|
| `screens/idea_detail_screen.dart` | 135 | `Color(0xFF6C5CE7)` | RadialMenuItem「碰撞」按钮色 |
| `screens/idea_detail_screen.dart` | 141 | `Color(0xFF00B894)` | RadialMenuItem「演化」按钮色 |
| `widgets/evolve_menu.dart` | 175 | `Color(0xFF6C5CE7)` | 渐变起点（碰撞） |
| `widgets/evolve_menu.dart` | 176 | `Color(0xFF00CEC9)` | 渐变终点（碰撞） |
| `widgets/evolve_menu.dart` | 209 | `Color(0xFF6C5CE7), Color(0xFFA29BFE)` | 渐变（碰撞按钮） |
| `widgets/evolve_menu.dart` | 220 | `Color(0xFF00B894), Color(0xFF55EFC4)` | 渐变（演化按钮） |

这 6 处属于「碰撞/演化」功能模块的视觉语言，应纳入 AppColors 作为 `collideAccent`/`evolveAccent` 等语义色，与重构目标一致。当前两文件重复硬编码，未来品牌色调整需要多处修改。

### 6.3 CustomPainter 颜色传递 ✅

`countdown_ring_painter.dart` 正确通过构造函数参数接收 `color` 和 `backgroundColor`，未在 `paint` 方法中调用 `AppColors.of(context)`（CustomPainter 不持有 BuildContext，正确做法）。`circle_painter.dart` 未检查但模式应一致。

### 6.4 主题切换死代码 ⚠️

`app.dart:18` 硬编码 `themeMode: ThemeMode.dark`，但后端 `User.dark_mode` 字段、前端 `SettingsService.darkMode` 字段都已建模。主题重构创造了完整的明暗色板（`AppColors.light` 和 `AppColors.dark`），但切换开关未接线，整套 light 主题实际上是死代码。详见 S2。

---

## 七、修复优先级建议

### P0（立即修复，发版阻断）

| 编号 | 问题 | 估时 | 影响 |
|------|------|------|------|
| B1 | 注册接口加 `@limiter.limit(REGISTER_LIMIT)` | 5 分钟 | 防止注册接口被刷爆 |
| B3 | AI 异常细节脱敏（`evolve.py:55,159`） | 15 分钟 | 防止内部信息泄露 |
| B2 | SSRF：`llm_api_url` 增加内网地址拦截 | 1-2 小时 | 防止内网探测和云凭证窃取 |
| B4 | 用户 API Key 加密存储 | 2-4 小时 | 防止数据库泄露导致 Key 外泄 |

**P0 建议同一 PR 完成**，B1/B3 改动小，B2/B4 需要补测试。

### P1（本迭代修复）

| 编号 | 问题 | 估时 |
|------|------|------|
| S1 | 硬编码颜色纳入 AppColors（碰撞/演化色） | 30 分钟 |
| S2 | `dark_mode` 设置接线或删除字段 | 1 小时 |
| S3 | `shouldRepaint` 补全字段判断 | 5 分钟 |
| S5 | `get_user_profile` 加限流 | 15 分钟 |
| S6 | 补充 auth/限流/SSRF 回归测试 | 半天 |

### P2（后续迭代）

| 编号 | 问题 | 估时 |
|------|------|------|
| S4 | `__import__("uuid")` 改为正常 import | 2 分钟 |
| S7 | `get_idea_detail` 查询优化 | 半天 |
| S8 | Web token 存储改 httpOnly Cookie | 1-2 天 |
| N1-N6 | 各种小清理 | 各 2-5 分钟 |

---

## 八、部署方式侦察结论

- **Flutter Web `<base href>`**：`frontend/web/index.html` 使用 `<base href="$FLUTTER_BASE_HREF">`，是 Flutter 默认占位符，构建时通过 `flutter build web --base-href=/your-path/` 替换。子路径部署支持完整。✅
- **后端 API 前缀**：`main.py:256` 统一 `prefix="/api"`，所有路由挂在 `/api/...` 下。✅
- **前端 API 调用层**：`api_client.dart` 用 `--dart-define=API_BASE_URL=...` 编译时注入，全文搜索 `/api/` 在 `frontend/lib/` 下零命中，无硬编码路径。✅
- **唯一隐患**：`backend/routers/users.py:93` 的 `RedirectResponse(url="/api/vault")` 硬编码路径，若 API 反向代理在非 `/` 根路径下会失效，但当前部署场景下无影响（已列入 Suggestion）。

---

**审查结论**：项目工程基础扎实，主题重构方向正确但收尾未完成。P0 的 4 个安全 Blocker 必须在下次发版前修复，其中 B1（注册限流）和 B3（异常脱敏）改动量极小但影响显著，建议立即处理。
