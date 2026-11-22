# IDEAS V2 阶段性 Demo 快速启动

> 目标：在本地浏览器体验当前 V2 分支的可运行功能。此 Demo 使用本地 SQLite 和 Mock AI，不连接生产数据库，也不代表生产部署完成。

## Demo 范围

当前分支前端已经包含以下页面/流程入口：

- Explore 创意探索、创意详情与血缘图
- 注册/登录
- 新建私有草稿、设置授权并发布
- Fork、Collide、Evolve
- 私有创意邀请收件箱与邀请管理
- 异步贡献、版本历史和公开版本时间线
- Vault、Spark、通知、个人资料

建议演示顺序：

1. 打开 Explore，查看系统预置的公开创意。
2. 注册两个测试账号，分别登录体验作者和协作者视角。
3. 新建创意，确认保存后默认为私有草稿。
4. 作者发布创意，选择授权条款和是否允许衍生。
5. 从允许衍生的公开创意执行 Fork；在详情页查看来源关系和授权快照。
6. 选择两个允许衍生的创意执行 Collide，检查双父血缘。
7. 从创意详情进入 Evolve，确认衍生结果和来源关系。
8. 用作者账号邀请第二个账号，接受后体验异步贡献和版本流程。

## 本地启动（推荐：SQLite + Mock AI）

要求：Python 3.11、Flutter stable、Chrome。

### 1. 启动后端

在终端 A：

```bash
cd idea-app/backend
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

pip install -r requirements.txt
```

先复制环境模板，再将数据库配置调整为本地 SQLite（避免连接任何现有 PostgreSQL）：

```powershell
Copy-Item .env.example .env
```

macOS / Linux 使用 `cp .env.example .env`。

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./dianzi_demo.db
DATABASE_URL_FALLBACK=sqlite+aiosqlite:///./dianzi_demo.db
APP_ENV=dev
DEEPSEEK_API_KEY=
JWT_SECRET=local-demo-only-change-this-value
CORS_ORIGINS=http://localhost:*,http://127.0.0.1:*
```

启动：

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8765 --reload
```

首次启动会创建本地 SQLite schema 并初始化演示内容。健康检查：

- API: http://127.0.0.1:8765/health
- Swagger: http://127.0.0.1:8765/docs

### 2. 启动 Flutter Web

在终端 B：

```bash
cd idea-app/frontend
flutter pub get
flutter run -d chrome --web-hostname 127.0.0.1 --web-port 8080 --dart-define=API_BASE_URL=http://127.0.0.1:8765/api
```

浏览器打开 http://127.0.0.1:8080 。

## AI 模式说明

- 默认 `DEEPSEEK_API_KEY=` 为空，使用项目 Mock 兜底，适合演示流程、页面和授权校验；AI 返回内容为预设结果，不是真实模型推理。
- 如需体验真实 AI，请在本地 `.env` 配置自己的模型 API Key 并重启后端。不要把 API Key 提交到 GitHub，也不要发到聊天中。

## 重要边界

- 这是本地开发 Demo，使用 SQLite；不用于并发压力测试或生产运行。
- 不连接生产 PostgreSQL，不执行 migrations 001/002/003，不导入真实用户数据。
- 本地 Demo 的 Mock AI 不代表真实模型效果。
- 最新 CI 会额外构建 Flutter Web 并上传 `ideas-v2-web-demo` artifact；该 artifact 是前端静态文件，单独打开不能替代 FastAPI 后端。
- 在线共享演示还需要可访问的演示后端、前端 API 地址、域名/CORS 与部署凭据；仓库现有自动部署 workflow 依赖 GitHub Actions secrets，目前不能仅凭代码存在就宣称已部署。

## 验收清单

- [ ] 后端 `/health` 返回正常。
- [ ] Web 页面可打开并成功连接 API。
- [ ] 注册/登录正常。
- [ ] 新建创意默认私有草稿。
- [ ] 发布时授权和衍生开关按选择保存。
- [ ] Fork/Collide/Evolve 成功创建关系，详情页可见谱系。
- [ ] 未允许衍生的来源被服务端拒绝。
- [ ] 多父来源中任一祖先禁止衍生时，后续衍生被拒绝。
- [ ] custom 授权未明确确认时被拒绝。
- [ ] 私有邀请在接受前不能访问，接受后访问生效。
