# 点子 App · 科学激发创意

[![status](https://img.shields.io/badge/status-beta-orange)](https://github.com/nihcya/ideas)
[![backend](https://img.shields.io/badge/backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![frontend](https://img.shields.io/badge/frontend-Flutter-02569B)](https://flutter.dev/)
[![ai](https://img.shields.io/badge/AI-DeepSeek-4B6BF7)](https://platform.deepseek.com/)

> 一个让 AI 帮你做创意碰撞、变体进化和灵感沉淀的小工具。
> 输入两个想法，让它们「碰撞」出新点子；选定一个方向，让它「进化」出多条变体；灵感来了用「火花」快速捕捉，值得留存的收进「保险箱」。

---

## ✨ 核心功能

| 功能 | 说明 |
|---|---|
| **碰撞 (Collide)** | 选两个点子，AI 从实用/跨领域/反常规等角度融合，产出 3 条碰撞方案 |
| **进化 (Evolve)** | 选定一个点子，用 SCAMPER 创新法（替代/适配/修改/复用/消除/反转）生成多条变体 |
| **火花 (Spark)** | 3 分钟倒计时的快速灵感捕获，写完自动淡出，防止思维被打断 |
| **点子库** | 浏览所有公开点子，按最新/最热/碰撞数排序 |
| **保险箱 (Vault)** | 收藏自己喜欢的点子，随时回看 |
| **裂变 (Fork)** | 基于已有点子分叉出新的版本，保留血缘关系 |
| **通知** | 碰撞/进化被确认、火花被回应等事件推送 |
| **多模型支持** | 可在个人设置里填入任意 OpenAI 兼容端点（DeepSeek / OpenAI / Kimi / 通义 / 智谱） |
| **Mock 兜底** | 没配 API Key 也能用，后端自动返回预设示例 |

## 🏗️ 技术栈

```
┌─────────────────────────────────────────────────┐
│                  浏览器 / 移动端                   │
│           Flutter Web / Android / iOS            │
└──────────────────────┬──────────────────────────┘
                       │ HTTP / REST (JSON)
┌──────────────────────▼──────────────────────────┐
│                   FastAPI 后端                    │
│  ┌─────────┐ ┌──────────┐ ┌───────────────────┐ │
│  │ JWT 鉴权 │ │ 速率限制 │ │ APScheduler 定时   │ │
│  └─────────┘ └──────────┘ └───────────────────┘ │
└──────┬──────────────┬────────────────┬───────────┘
       │              │                │
┌──────▼──────┐ ┌─────▼─────┐ ┌───────▼────────┐
│ PostgreSQL  │ │  Redis    │ │ DeepSeek API   │
│ (主库)       │ │ (缓存/限流)│ │ (LLM 调用)     │
│ SQLite 兜底  │ │ 内存兜底   │ │ Mock 兜底      │
└─────────────┘ └───────────┘ └────────────────┘
```

- **前端**: Flutter 3.x + Dart 3.x · flutter_riverpod (状态管理) · go_router (路由) · dio (网络) · flutter_secure_storage (安全存储)
- **后端**: FastAPI 0.115 · SQLAlchemy 2.0 (async) · asyncpg / psycopg2 · redis-py · python-jose + passlib[bcrypt] (JWT) · apscheduler (定时) · slowapi (限流) · pydantic-settings (配置)
- **AI**: OpenAI 兼容协议客户端，支持任意端点；DeepSeek 官方推荐

## 📁 项目结构

```
ideas/
├── README.md
├── idea-app/                     # 全部源码
│   ├── backend/
│   │   ├── main.py               # FastAPI 入口 + lifespan + scheduler
│   │   ├── config.py             # pydantic-settings 配置加载
│   │   ├── database.py           # 引擎初始化（PG 优先 / SQLite 兜底）
│   │   ├── requirements.txt
│   │   ├── .env.example          # 开发环境配置模板
│   │   ├── .env.prod.example     # 生产环境配置模板
│   │   ├── Dockerfile
│   │   ├── db/
│   │   │   ├── schema.sql        # 建表脚本
│   │   │   └── seed.sql          # 种子数据
│   │   ├── models/               # SQLAlchemy ORM 模型
│   │   ├── schemas/              # Pydantic 请求/响应模型
│   │   ├── routers/              # 路由：auth / ideas / evolve / spark / vault / ...
│   │   ├── services/             # 业务服务：JWT / 审计 / 缓存 / DeepSeek / 限流 / ...
│   │   ├── prompts/              # AI 提示词模板
│   │   └── tests/
│   ├── frontend/
│   │   ├── pubspec.yaml
│   │   ├── lib/
│   │   │   ├── main.dart / app.dart
│   │   │   ├── routers/          # go_router 路由表
│   │   │   ├── providers/        # Riverpod providers
│   │   │   ├── screens/          # 各页面
│   │   │   ├── services/         # API 客户端 / 本地存储
│   │   │   ├── models/           # 数据模型
│   │   │   ├── widgets/          # 可复用组件
│   │   │   └── theme/            # 主题 & 颜色系统
│   │   └── web/ android/ ios/ linux/ macos/ windows/
│   ├── docker-compose.yml        # 本地开发（Postgres + Redis）
│   ├── docker-compose.prod.yml   # 生产部署
│   ├── nginx/                    # Nginx 配置
│   └── docs/                     # API_SPEC / DEPLOYMENT_GUIDE / SECURITY_REPORT ...
└── .gitignore
```

## 🚀 快速开始

### 方案 A：最简单（SQLite + Mock，不需要任何外部服务）

适合快速跑通全流程，演示用。

```bash
# 1. 后端
cd idea-app/backend
python -m venv venv
venv\Scripts\activate           # Windows
pip install -r requirements.txt
copy .env.example .env          # 用默认值即可，数据库自动兜底 SQLite
python -m uvicorn main:app --host 127.0.0.1 --port 8765 --reload

# 2. 前端
cd idea-app/frontend
flutter pub get
flutter run -d web-server --web-hostname 127.0.0.1 --web-port 8080
```

浏览器打开 http://127.0.0.1:8080 ，API 文档在 http://127.0.0.1:8765/docs 。

> 没配 `DEEPSEEK_API_KEY` 时自动 Mock，碰撞/进化返回预设示例。

### 方案 B：Docker Compose（Postgres + Redis）

适合本地开发时用真实数据库。

```bash
cd idea-app
docker compose up -d            # 启动 Postgres 16 + Redis 7
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8765
```

Postgres 首次启动会自动执行 `db/schema.sql` 和 `db/seed.sql`（种子数据）。

### 环境变量

复制 `backend/.env.example` 为 `backend/.env`，按需要修改：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://dianzi:dianzi_dev_pwd@localhost:5432/dianzi_app` | 主数据库（Postgres） |
| `DATABASE_URL_FALLBACK` | `sqlite+aiosqlite:///./dianzi_dev.db` | PG 不可用时自动降级 |
| `REDIS_URL` | `redis://localhost:6379/0` | 缓存 + 限流 |
| `DEEPSEEK_API_KEY` | *(空)* | 留空则 Mock |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | 可换其他 OpenAI 兼容端点 |
| `JWT_SECRET` | *(空)* | **生产必须设置** |
| `LLM_KEY_ENCRYPTION_KEY` | *(空)* | 加密用户自定义 API Key，生产必须设置 |
| `APP_ENV` | `dev` | `dev` / `prod` |
| `CORS_ORIGINS` | `http://localhost:*,http://127.0.0.1:*` | prod 必须用精确域名 |

### Windows 开发提示

- Flutter SDK 路径（本项目约定）：`e:\GithubFiles\ideas\.flutter`，包装脚本在 `e:\GithubFiles\ideas\.flutter-bin\flutter.bat`
- `flutter pub get` 报 "symlink support"：启用 **Windows 开发者模式**（`设置 → 系统 → 开发者选项 → 开发人员模式`）

## 📡 API 概览

全部接口挂在 `/api` 前缀下，主入口 `http://127.0.0.1:8765/api`，Swagger 文档在 `/docs`。

| 分组 | 方法 | 路径 | 说明 |
|---|---|---|---|
| **Auth** | POST | `/api/auth/register` | 注册 |
| | POST | `/api/auth/login` | 登录（返回 JWT） |
| | POST | `/api/auth/logout` | 登出 |
| **Ideas** | GET | `/api/ideas/explore` | 探索列表（分页 + 排序） |
| | GET | `/api/ideas/{id}` | 点子详情 |
| | POST | `/api/ideas` | 发布点子 |
| | POST | `/api/ideas/fork` | 裂变（基于另一个点子创建变体） |
| **Evolve** | POST | `/api/ideas/collide` | 碰撞：两个点子 → 3 条融合方案 |
| | POST | `/api/ideas/collide/confirm` | 确认碰撞方案（入库为新点子） |
| | POST | `/api/ideas/evolve` | 进化：一个点子 → SCAMPER 变体 |
| | POST | `/api/ideas/evolve/confirm` | 确认进化方案 |
| **Spark** | GET | `/api/spark/today` | 今日火花列表 |
| | POST | `/api/spark/draft` | 草稿 |
| | POST | `/api/spark/submit` | 提交 |
| **Vault** | GET | `/api/vault` | 保险箱收藏 |
| | POST | `/api/vault/{id}/collect` | 收藏 |
| | DELETE | `/api/vault/{id}` | 取消收藏 |
| **Settings** | GET | `/api/settings` | 用户设置（含自定义 LLM 配置） |
| | PUT | `/api/settings` | 更新设置 |
| **Notifications** | GET | `/api/notifications` | 通知列表 |
| | POST | `/api/notifications/read` | 标记已读 |

> 详细字段定义见 [idea-app/API_SPEC.md](idea-app/API_SPEC.md)

## 🌐 部署

生产部署用 Docker Compose + Nginx 反代 + HTTPS，参考：

- [idea-app/DEPLOYMENT_GUIDE.md](idea-app/DEPLOYMENT_GUIDE.md) — 完整部署指南
- [idea-app/docker-compose.prod.yml](idea-app/docker-compose.prod.yml) — 生产 compose 文件
- [idea-app/nginx/nginx-https.conf](idea-app/nginx/nginx-https.conf) — Nginx HTTPS 配置

最简流程：

```bash
# 前端构建
cd idea-app/frontend
flutter build web --release --dart-define=API_BASE_URL=https://your-domain.com/api

# 后端 + 数据库 + Nginx
cd idea-app
docker compose -f docker-compose.prod.yml up -d
```

## 📝 项目状态

- **当前版本**: v1.3
- **后端框架**: FastAPI 0.115 · Python 3.11
- **前端框架**: Flutter 3.47 · Dart 3.13
- **数据库**: PostgreSQL 16（生产）/ SQLite（开发兜底）
- **缓存**: Redis 7（生产）/ 内存兜底
- **AI**: DeepSeek deepseek-chat / 任意 OpenAI 兼容端点 / Mock 兜底

### 已实现
- ✅ 用户注册登录（JWT + bcrypt）
- ✅ 点子 CRUD + 裂变
- ✅ 碰撞（Collide）+ 进化（Evolve）两套 AI 工作流
- ✅ 火花（Spark）3 分钟限时捕获
- ✅ 保险箱收藏
- ✅ 通知中心
- ✅ 速率限制（slowapi）
- ✅ 安全审计日志
- ✅ 用户自定义 LLM 端点 + API Key 加密存储
- ✅ SQLite 自动兜底（零依赖本地开发）
- ✅ Mock 模式（无 API Key 自动启用）
- ✅ GitHub Actions 自动部署 Web 构建产物

### 规划中
- 🔲 社交关系（关注 / 粉丝）
- 🔲 点子血缘可视化（裂变树）
- 🔲 移动端原生壳（iOS / Android 打包）
- 🔲 管理员后台

## 📄 许可证

MIT License
