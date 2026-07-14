# 5 个 Critical 问题解决方案

> 本文档描述阻塞上线的 5 个 Critical 问题的修复方案，审核通过后执行。

---

## C1: 密钥泄露风险

### 问题描述

`backend/.env.prod` 包含真实 JWT_SECRET、PG密码、Redis密码和 DeepSeek API Key，该文件存在于项目目录中，`.gitignore` 仅排除了 `.env` 但未排除 `.env.prod`，有被提交到 Git 仓库泄露的风险。

### 解决方案

**步骤 1：更新 `.gitignore`，增加 `.env.prod` 排除规则**

文件：`.gitignore`

```diff
 .env
+.env.prod
+.env.local
+.env.*.prod
```

**步骤 2：删除项目目录中的 `backend/.env.prod` 文件**

该文件是部署时使用的本地副本，不应留在代码仓库中。服务器上已有独立的 `.env` 文件运行，删除本地副本不影响线上。

**步骤 3：创建 `.env.prod.example` 模板文件（脱敏）**

文件：`backend/.env.prod.example`

将 `.env.prod` 的结构保留，所有敏感值替换为占位符，供部署参考：

```env
APP_ENV=prod
APP_HOST=0.0.0.0
APP_PORT=8000

JWT_SECRET=<生成64位随机串: openssl rand -hex 32>
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=7

PG_PASSWORD=<你的PG密码>
REDIS_PASSWORD=<你的Redis密码>

DATABASE_URL=postgresql+asyncpg://dianzi:<PG_PASSWORD>@postgres:5432/dianzi_app
REDIS_URL=redis://:<REDIS_PASSWORD>@redis:6379/0

DEEPSEEK_API_KEY=<你的DeepSeek API Key>
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

CORS_ORIGINS=https://your-domain.com

SPARK_DURATION_SECONDS=180
FADE_FADING_DAYS=7
FADE_FADED_DAYS=8
IDEA_MAX_LENGTH=300

DIANZI_SCHEDULER_ENABLED=1
```

**步骤 4（需用户手动执行）：轮换已泄露的密钥**

- 在 DeepSeek 控制台重新生成 API Key，作废旧 Key
- 重新生成 JWT_SECRET
- 更新服务器上的 `.env` 文件

### 涉及文件

| 文件 | 操作 |
|------|------|
| `.gitignore` | 编辑：增加 `.env.prod` 等排除规则 |
| `backend/.env.prod` | 删除 |
| `backend/.env.prod.example` | 新建：脱敏模板 |

---

## C2: 无 HTTPS — JWT 和密码明文传输

### 问题描述

生产环境使用 HTTP 明文传输，JWT token 和用户密码在网络中可被中间人截获。Nginx 配置中已预留 HTTPS 注释但未实施。

### 解决方案

**注意：此问题需要域名和服务器操作，代码层面仅准备 Nginx 配置模板，实际部署需用户在服务器上执行。**

**步骤 1：准备 Nginx HTTPS 配置模板**

文件：`deploy/nginx-https.conf`（新建，供服务器参考）

```nginx
# HTTP → HTTPS 强制跳转
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

# HTTPS 主配置
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL 证书路径（certbot 默认位置）
    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # 安全响应头
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 前端静态文件
    root /opt/dianzi/web;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反代
    location /api/ {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 健康检查（不记日志）
    location /health {
        proxy_pass http://127.0.0.1:8765;
        access_log off;
    }
}
```

**步骤 2：更新 `.env.prod.example` 中 CORS 配置**

将 CORS 从 IP + localhost 改为仅域名：

```env
# HTTPS 部署后，CORS 仅允许正式域名
CORS_ORIGINS=https://your-domain.com
```

**步骤 3：修复全局异常处理器泄露内部错误细节**

文件：`backend/main.py` 第 228-236 行

```python
# 修改前：
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    print(f"[error] unhandled: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
    )

# 修改后：
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    print(f"[error] unhandled: {exc}\n{traceback.format_exc()}")
    # 生产环境不泄露内部错误细节
    safe_message = "服务器内部错误" if settings.app_env == "prod" else str(exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": safe_message}},
    )
```

**步骤 4（需用户在服务器手动执行）：部署 HTTPS**

```bash
# 1. 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 2. 申请证书（需先有域名 A 记录指向服务器 IP）
sudo certbot --nginx -d your-domain.com

# 3. 替换 Nginx 配置
sudo cp deploy/nginx-https.conf /etc/nginx/sites-available/dianzi
sudo nginx -t && sudo systemctl reload nginx
```

### 涉及文件

| 文件 | 操作 |
|------|------|
| `deploy/nginx-https.conf` | 新建：HTTPS Nginx 配置模板 |
| `backend/main.py` | 编辑：异常处理器生产环境脱敏 |
| `backend/.env.prod.example` | 编辑：CORS 改为域名（C1 步骤中已创建） |

---

## C3: 无限流 — 登录可暴力破解、AI 接口可被刷量

### 问题描述

全项目无速率限制。API_SPEC.md 中定义了 429 RATE_LIMITED 错误码但从未实现。登录接口可被暴力破解，AI 调用接口（collide/evolve）可被刷量消耗 DeepSeek 配额。

### 解决方案

**步骤 1：添加 slowapi 依赖**

文件：`backend/requirements.txt`

```diff
 aiosqlite==0.20.0
+slowapi==0.1.9
```

**步骤 2：创建限流配置模块**

文件：`backend/services/rate_limit.py`（新建）

```python
"""速率限制配置 — 基于 slowapi"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# 按 IP 限流
limiter = Limiter(key_func=get_remote_address)


def rate_limit_message_handler(request, response, limit):
    """自定义 429 响应体，保持统一错误格式。"""
    return response.headers.setdefault(
        "Content-Type", "application/json"
    )


# 预设限流规则
LOGIN_LIMIT = "10/minute"          # 登录：每分钟 10 次
REGISTER_LIMIT = "5/minute"        # 注册：每分钟 5 次
AI_LIMIT = "10/minute"             # AI 接口：每分钟 10 次
CREATE_LIMIT = "20/minute"         # 创建点子：每分钟 20 次
```

**步骤 3：在 main.py 注册限流器**

文件：`backend/main.py`

```python
# 在 app 创建后添加：
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from services.rate_limit import limiter

app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMITED", "message": "请求过于频繁，请稍后再试"}},
    )
```

**步骤 4：在关键端点添加限流装饰器**

文件：`backend/routers/auth.py`

```python
from services.rate_limit import limiter, LOGIN_LIMIT, REGISTER_LIMIT

@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit(REGISTER_LIMIT)
async def register(request: Request, req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    ...

@router.post("/login", response_model=AuthResponse)
@limiter.limit(LOGIN_LIMIT)
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    ...
```

文件：`backend/routers/evolve.py`

```python
from services.rate_limit import limiter, AI_LIMIT

@router.post("/collide", response_model=CollideResponse)
@limiter.limit(AI_LIMIT)
async def collide(request: Request, req: CollideRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ...

@router.post("/evolve", response_model=EvolveResponse)
@limiter.limit(AI_LIMIT)
async def evolve(request: Request, req: EvolveRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ...
```

文件：`backend/routers/ideas.py`

```python
from services.rate_limit import limiter, CREATE_LIMIT

@router.post("", response_model=IdeaResponse, status_code=201)
@limiter.limit(CREATE_LIMIT)
async def create_idea(request: Request, req: IdeaCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ...
```

**注意**：slowapi 的 `@limiter.limit` 要求被装饰的函数第一个参数必须是 `request: Request`，因此需要调整函数签名。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `backend/requirements.txt` | 编辑：添加 slowapi |
| `backend/services/rate_limit.py` | 新建：限流配置 |
| `backend/main.py` | 编辑：注册限流器和异常处理 |
| `backend/routers/auth.py` | 编辑：登录/注册加速流 |
| `backend/routers/evolve.py` | 编辑：碰撞/演化加速流 |
| `backend/routers/ideas.py` | 编辑：创建点子加速流 |

---

## C4: 淡出逻辑 Bug — 未 Fork 点子永不物理删除

### 问题描述

`fade_service.py` 中 `check_and_fade` 函数的执行流程：

1. 步骤 1：`active` → `fading`（7天未触碰）
2. 步骤 2：删除过期的 `vault_items`（8天未触碰）
3. 步骤 3：物理删除 `status='faded'` 且未被 fork 的点子

**Bug**：全流程中没有任何步骤将 `status` 从 `fading` 更新为 `faded`。步骤 3 查询 `status='faded'` 永远不会命中，导致未 fork 的过期点子永远不会被物理删除，数据库持续膨胀。

### 解决方案

在步骤 2（删除 vault_items）之后、步骤 3（物理删除）之前，增加一个步骤：将已移出仓库的 `fading` 点子更新为 `faded`。

文件：`backend/services/fade_service.py`

```python
async def check_and_fade(db: AsyncSession) -> dict:
    """执行淡出检查：7天未触碰→fading，8天未触碰→移出仓库→faded→物理删除。"""
    now = datetime.now(timezone.utc)
    fading_threshold = now - timedelta(days=settings.fade_fading_days)
    faded_threshold = now - timedelta(days=settings.fade_faded_days)

    # 1. 更新 status='fading'：7天未触碰
    fade_result = await db.execute(
        text("""
            UPDATE ideas SET status = 'fading'
            WHERE id IN (
                SELECT i.id FROM vault_items vi
                JOIN ideas i ON i.id = vi.idea_id
                WHERE i.status = 'active'
                  AND vi.last_touch_at < :fading_threshold
            )
        """),
        {"fading_threshold": fading_threshold},
    )
    faded_count = fade_result.rowcount if hasattr(fade_result, "rowcount") else 0

    # 2. 移出仓库：8天未触碰
    remove_result = await db.execute(
        text("""
            DELETE FROM vault_items
            WHERE last_touch_at < :faded_threshold
        """),
        {"faded_threshold": faded_threshold},
    )
    removed_count = remove_result.rowcount if hasattr(remove_result, "rowcount") else 0

    # 3. 【新增】将已移出仓库的 fading 点子标记为 faded
    #    条件：status='fading' 且该点子已不在任何仓库中（vault_items 中无记录）
    mark_result = await db.execute(
        text("""
            UPDATE ideas SET status = 'faded'
            WHERE status = 'fading'
              AND id NOT IN (SELECT idea_id FROM vault_items)
        """),
    )
    marked_count = mark_result.rowcount if hasattr(mark_result, "rowcount") else 0

    # 4. 物理删除未被 fork 的 faded 点子
    delete_result = await db.execute(
        text("""
            DELETE FROM ideas
            WHERE status = 'faded'
              AND id NOT IN (
                  SELECT parent_id FROM fork_relations
                  UNION
                  SELECT child_id FROM fork_relations
              )
        """),
    )
    deleted_count = delete_result.rowcount if hasattr(delete_result, "rowcount") else 0

    await db.commit()
    return {
        "faded_to_fading": faded_count,
        "removed_from_vault": removed_count,
        "marked_as_faded": marked_count,
        "physically_deleted": deleted_count,
    }
```

### 涉及文件

| 文件 | 操作 |
|------|------|
| `backend/services/fade_service.py` | 编辑：新增步骤 3（fading→faded 状态转换） |

---

## C5: 前端假实现 + Spark 倒计时 Bug

### 5a: 设置页"通知开关"和"清除缓存"假实现

#### 问题描述

- `settings_screen.dart` 第 23 行 `_notifyEnabled = true` 仅本地 state，切换开关不调用后端 API，重启后丢失
- 第 106-115 行 `_clearCache()` 仅 `Future.delayed(500ms)` 后弹 SnackBar，未执行任何实际清理

#### 解决方案

**方案：移除假实现的功能，保留真实可用的功能**

"通知开关"需要后端推送服务（FCM/APNs）支持，当前后端未实现推送能力，移除该开关比保留假实现更诚实。"清除缓存"在前端 Web 场景下无实际缓存可清（Dio 不做 HTTP 缓存），移除比假装执行更好。

文件：`frontend/lib/screens/settings_screen.dart`

```dart
// 删除 _notifyEnabled 和 _clearing 状态变量
// 删除 _clearCache() 方法

// 在 build 方法中：
// 1. 删除"通用"分区中的"通知"SwitchListTile
// 2. 删除"其他"分区中的"清除缓存"ListTile
// 3. "通用"分区仅保留"深色模式"（固定开启）
// 4. "其他"分区仅保留"关于"
```

具体改动：

- 删除 `bool _notifyEnabled = true;` 和 `bool _clearing = false;`
- 删除整个 `_clearCache()` 方法
- 删除"通知"SwitchListTile 组件
- 删除"清除缓存"ListTile 组件
- 保留"深色模式"和"关于"

### 5b: Spark 倒计时归零重复触发自动保存

#### 问题描述

`spark_screen.dart` 第 47-65 行 `_startCountdown` 逻辑：

```dart
_countdownTimer = Timer.periodic(const Duration(seconds: 1), (t) {
  setState(() {
    if (_remaining <= 0) {        // ← 第 55 行
      t.cancel();
      _autoSaveDraft();            // ← 归零后每次 tick 都会触发
    } else {
      _remaining -= 1;
      if (_remaining == 0) {       // ← 第 60 行
        _autoSaveDraft();          // ← 倒计时到 0 时也触发
      }
    }
  });
});
```

当 `_remaining` 递减到 0 时，先走 else 分支（`_remaining == 0` 调用 `_autoSaveDraft()`），下一次 tick 时走 if 分支（`_remaining <= 0` 再次调用 `_autoSaveDraft()`），导致草稿被保存两次。

#### 解决方案

增加 `_countdownEnded` 标志位，确保 `_autoSaveDraft` 只调用一次。

文件：`frontend/lib/screens/spark_screen.dart`

```dart
// 新增状态变量
bool _countdownEnded = false;

// 修改 _startCountdown
void _startCountdown() {
  _countdownTimer?.cancel();
  _countdownTimer = Timer.periodic(const Duration(seconds: 1), (t) {
    if (!mounted) {
      t.cancel();
      return;
    }
    setState(() {
      if (_remaining <= 0) {
        if (!_countdownEnded) {
          _countdownEnded = true;
          t.cancel();
          _autoSaveDraft();
        }
      } else {
        _remaining -= 1;
        if (_remaining == 0 && !_countdownEnded) {
          _countdownEnded = true;
          _autoSaveDraft();
        }
      }
    });
  });
}
```

### 5c: Spark 已提交视图无法显示内容（附带修复）

#### 问题描述

`_SubmittedView` 使用 `controller.text` 显示用户提交的内容，但页面重建后 `_ctrl` 是新的空 controller，显示"（无内容）"。

#### 解决方案

提交成功后将内容存入 state 变量，`_SubmittedView` 从 state 读取而非 controller。

文件：`frontend/lib/screens/spark_screen.dart`

```dart
// 新增状态变量
String? _submittedContent;

// 修改 _submit 方法，提交成功后保存内容
Future<void> _submit() async {
  final content = _ctrl.text.trim();
  if (content.isEmpty) {
    ...
  }
  setState(() => _submitting = true);
  try {
    final result = await ref.read(sparkTodayProvider.notifier).submit(content);
    _countdownTimer?.cancel();
    _debounceTimer?.cancel();
    if (mounted) {
      setState(() => _submittedContent = content);  // 保存内容
      context.pushReplacement('/idea/${result.id}');
    }
  } ...
}

// 修改 build 方法中 _SubmittedView 的调用
// 从：_SubmittedView(spark: spark, controller: _ctrl)
// 改为：_SubmittedView(spark: spark, content: _submittedContent)

// 修改 _SubmittedView 类
class _SubmittedView extends StatelessWidget {
  final SparkToday spark;
  final String? content;
  const _SubmittedView({required this.spark, this.content});

  @override
  Widget build(BuildContext context) {
    ...
    // 从：controller.text.isEmpty ? '（无内容）' : controller.text
    // 改为：(content == null || content!.isEmpty) ? '（无内容）' : content!
    ...
  }
}
```

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/lib/screens/settings_screen.dart` | 编辑：移除假实现的通知开关和清除缓存 |
| `frontend/lib/screens/spark_screen.dart` | 编辑：修复倒计时重复保存 + 已提交内容显示 |

---

## 执行顺序

1. **C1** — 更新 .gitignore、删除 .env.prod、创建 .env.prod.example
2. **C4** — 修复 fade_service.py 逻辑 Bug（最小改动，最高风险消除）
3. **C3** — 添加速率限制（新增文件 + 多文件编辑）
4. **C2** — 修复异常处理器脱敏 + 创建 Nginx HTTPS 配置模板
5. **C5** — 修复前端假实现和 Spark Bug

## 不在本次范围内（需用户手动操作）

- 在 DeepSeek 控制台轮换 API Key（C1）
- 在服务器上重新生成 JWT_SECRET 并更新 .env（C1）
- 购买域名 + 配置 A 记录 + certbot 申请 SSL 证书（C2）
- 在服务器上部署 Nginx HTTPS 配置（C2）

---

> 请审核以上方案。审核通过后我将按执行顺序依次修改代码。
