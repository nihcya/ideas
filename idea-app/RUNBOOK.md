# RUNBOOK — 点子 App 验收指南

> 早安！这是你昨晚让我开发的"点子 App"项目的运行手册。
> 按下面的步骤操作，5 分钟内就能跑起来。

---

## 0. 项目现状速览

| 模块 | 状态 | 说明 |
|------|------|------|
| 后端 FastAPI | ✅ 已跑通 | 22 个 API 端点全部可用，SQLite 兜底（无需装 PostgreSQL） |
| 数据库 | ✅ 已初始化 | 30 条 PGC 点子 + 30 天今日一点题库 + 14 个违禁词 |
| AI 功能 | ✅ Mock 兜底 | DeepSeek API Key 留空时自动返回预设创意方案 |
| Flutter 前端 | ✅ 代码完成 | 32 个 dart 文件，需安装 Flutter SDK 后运行 |
| 真机震动测试 | ❌ 未完成 | 需要真机或模拟器 |

---

## 1. 启动后端（3 分钟）

### 1.1 进入后端目录

```powershell
cd f:\treaFiles\Ideas\ideas\idea-app\backend
```

### 1.2 激活虚拟环境

```powershell
.\venv\Scripts\Activate.ps1
```

如果提示"禁止运行脚本"，先执行：
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 1.3 启动服务

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

看到以下输出说明成功：
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 1.4 验证后端

浏览器打开 http://127.0.0.1:8000/docs —— 能看到 Swagger API 文档即成功。

快速测试：
```powershell
# 健康检查
curl http://127.0.0.1:8000/health

# 探索页（无需登录）
curl http://127.0.0.1:8000/api/ideas/explore
```

---

## 2. 安装 Flutter SDK（5 分钟）

### 2.1 下载 Flutter

推荐用 Git clone（不需要手动下载 zip）：

```powershell
cd f:\treaFiles
git clone https://github.com/flutter/flutter.git -b stable
```

### 2.2 配置环境变量

把 Flutter 加入 PATH（永久生效）：

```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";f:\treaFiles\flutter\bin", [EnvironmentVariableTarget]::User)
```

**关闭并重新打开 PowerShell**，然后验证：

```powershell
flutter --version
flutter doctor
```

### 2.3 配置 Android Studio / Chrome

`flutter doctor` 会告诉你缺什么。最简方案：
- **Chrome 浏览器**：用于 Web 调试（最快）
- **Android Studio**：用于 Android 模拟器（需装 SDK + 创建 AVD）

---

## 3. 启动前端（2 分钟）

### 3.1 确保后端在运行

后端必须先启动（步骤 1），前端才能调 API。

### 3.2 安装依赖

```powershell
cd f:\treaFiles\Ideas\ideas\idea-app\frontend
flutter pub get
```

### 3.3 修改 API 地址（如需）

如果你用 **Android 模拟器**，需要把 API 地址改为 `10.0.2.2`：

编辑 `lib/services/api_client.dart` 第 7 行：
```dart
const String kApiBaseUrl = 'http://10.0.2.2:8000/api';  // Android 模拟器
```

如果你用 **Chrome / Windows 桌面**，保持 `127.0.0.1` 即可。

### 3.4 运行

```powershell
# Web 版（最快验证）
flutter run -d chrome

# Windows 桌面版
flutter run -d windows

# Android 模拟器
flutter run -d emulator-5554
```

---

## 4. 验收清单

启动后按这个清单逐项验证：

### 后端 API（已验证 ✅）
- [ ] `GET /health` 返回 `{"status":"ok"}`
- [ ] `GET /api/ideas/explore` 返回 30 个圆圈
- [ ] `POST /api/auth/register` 注册成功，返回 token
- [ ] `POST /api/auth/login` 登录成功，返回 token
- [ ] `POST /api/ideas`（带 token）发布点子成功
- [ ] `GET /api/vault`（带 token）返回仓库列表
- [ ] `GET /api/spark/today`（带 token）返回今日题目
- [ ] `GET /api/notifications`（带 token）返回通知列表

### Flutter 前端
- [ ] App 启动，显示暗色主题
- [ ] 底部 4 个 Tab：探索 / 仓库 / 一点 / 我
- [ ] 探索页显示彩色圆圈（CustomPainter 渲染，非 GridView）
- [ ] 圆圈有浮动动效（±5px，3 秒周期）
- [ ] 点击圆圈跳转详情页 + 震动反馈
- [ ] 详情页显示大圆圈 + 内容 + 作者 + 谱系图
- [ ] 详情页底部有 Fork / 收集 / 演化三个按钮
- [ ] 演化按钮弹出底部菜单（碰撞 + 演化）
- [ ] 注册/登录页表单校验（用户名 3-20，密码 ≥8）
- [ ] 今日一点页 3 分钟倒计时
- [ ] 仓库页统计卡（自己产生 / 收集 / 被 Fork）

---

## 5. 已知限制

1. **DeepSeek AI 是 Mock**：`DEEPSEEK_API_KEY` 留空，碰撞/演化返回预设方案。配置真实 Key 后自动切换。
2. **数据库是 SQLite**：未装 PostgreSQL，自动降级为 SQLite。数据存在 `backend/dianzi_dev.db`。
3. **Redis 是内存字典**：未装 Redis，缓存退化为进程内存。
4. **真机震动未测**：`HapticFeedback` 在 Web 版无效，需真机或模拟器。
5. **圆圈布局是伪随机**：基于 ideaId.hashCode 做种子，相同数据相同布局。

---

## 6. 配置真实 DeepSeek（可选）

编辑 `backend/.env`：
```
DEEPSEEK_API_KEY=sk-your-real-key-here
```

重启后端即可。AI 碰撞/演化/审核会切换为真实调用。

---

## 7. 目录结构

```
idea-app/
├── backend/                 # FastAPI（已跑通）
│   ├── venv/                # Python 虚拟环境
│   ├── models/              # 10 个 SQLAlchemy 模型
│   ├── schemas/             # 8 个 Pydantic schema
│   ├── routers/             # 8 个 router，22 个端点
│   ├── services/            # DeepSeek/缓存/审核/淡出/今日一点
│   ├── db/                  # schema.sql + seed.sql
│   ├── config.py
│   ├── database.py          # PG→SQLite 自动降级
│   ├── main.py              # FastAPI + APScheduler
│   └── dianzi_dev.db        # SQLite 数据文件（自动生成）
├── frontend/                # Flutter（代码完成）
│   └── lib/
│       ├── models/          # 6 个数据模型
│       ├── services/        # 8 个 API 服务
│       ├── providers/       # 8 个 Riverpod provider
│       ├── widgets/         # 4 个核心 widget
│       ├── screens/         # 10 个页面
│       ├── routers/         # go_router 路由
│       ├── theme/           # 暗色主题
│       ├── main.dart
│       └── app.dart
├── TREA_CONTEXT.md          # 项目总览
├── API_SPEC.md              # API 规格
├── DB_SCHEMA.md             # 数据库 DDL
├── TECH_CONSTRAINTS.md      # 技术约束
└── RUNBOOK.md               # 本文件
```

---

## 8. 常见问题

**Q: 后端启动报 `ConnectionRefusedError`？**
A: 这是 PostgreSQL 不可用的正常现象，会自动降级到 SQLite。看到 `PostgreSQL unavailable, falling back to SQLite` 即可。

**Q: Flutter `pub get` 报错？**
A: 确认 `flutter --version` 能正常输出。如果网络问题，试 `flutter pub get --offline` 或配置镜像：
```powershell
$env:PUB_HOSTED_URL="https://pub.flutter-io.cn"
$env:FLUTTER_STORAGE_BASE_URL="https://storage.flutter-io.cn"
flutter pub get
```

**Q: Web 版没有震动反馈？**
A: 正常。`HapticFeedback` 只在真机/模拟器生效。Web 版功能正常但无震动。

**Q: 圆圈点击没反应？**
A: 检查后端是否在运行（`http://127.0.0.1:8000/health`）。前端依赖后端 API。
```

---

晚安。早安。
