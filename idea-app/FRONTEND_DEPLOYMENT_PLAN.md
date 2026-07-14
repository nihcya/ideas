# 电子点子 App 前端项目部署计划文档

| 项目名称   | 电子点子 App（Dianzi App）— 前端                |
| ------ | ---------------------------------------- |
| 文档版本   | v1.1                                     |
| 编制日期   | 2026-07-09                               |
| 文档状态   | ✅ 已执行（前端已上线）                             |
| 前端技术栈  | Flutter Web 3.24+                        |
| 目标服务器  | 124.221.108.59（Ubuntu 22.04，已部署后端）       |
| 部署模式   | Flutter Web 构建产物 + Nginx 静态托管            |
| 服务地址  | http://124.221.108.59                    |
| 当前版本  | v1.0.0-202607092045                      |

## 修订记录

| 版本   | 日期         | 修订人   | 修订内容                                    |
| ---- | ---------- | ----- | --------------------------------------- |
| v1.0 | 2026-07-09 | AI 助手 | 初始版本，含完整部署流程与 CI/CD                    |
| v1.1 | 2026-07-09 | AI 助手 | 部署完成后更新：补充实际部署结果、API 硬编码修复、构建参数、验证数据 |

---

## 一、项目概述

### 1.1 部署目标

将电子点子 App 的 Flutter Web 前端构建为静态资源，部署到已运行后端服务的服务器，实现：

- 前后端**同站部署**（Nginx 同时 serve 前端静态文件 + 反代后端 API）
- 用户通过 `http://124.221.108.59` 直接访问 Web 应用
- 部署过程**可重复、可追溯、可回滚**
- 为后续 CI/CD 自动化奠定基础

### 1.2 技术选型依据

| 技术选型            | 选型依据                                          |
| --------------- | --------------------------------------------- |
| Flutter Web     | 复用移动端代码，一套 Dart 代码支持 iOS/Android/Web 多端      |
| Nginx 静态托管      | 后端已用 Nginx 反代，复用现有实例；静态资源 serve 性能优于 Node 服务 |
| Riverpod 状态管理   | 编译时安全、可测试性强，社区活跃                             |
| Dio 网络层         | 拦截器机制完善，便于统一处理 JWT 认证与 401 跳转                 |
| go_router 路由    | 声明式路由，支持深链接与 Web 端 URL 直达                    |
| dart-define 环境注入 | 编译时注入 API 地址，无需运行时配置文件，安全性高                   |

### 1.3 部署架构

```
互联网用户（浏览器）
    │
    ▼
┌──────────────────────────────────────────┐
│ 服务器 124.221.108.59                     │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │ Nginx (80)                       │    │
│  │  ├─ location / → 前端静态文件       │    │
│  │  │   └─ /opt/dianzi/frontend/web │    │
│  │  ├─ location /api/ → 反代后端      │    │
│  │  └─ location /docs → API 文档     │    │
│  └──────────┬──────────────────────┘    │
│             │                            │
│  ┌──────────▼──────────────────────┐    │
│  │ Backend (127.0.0.1:8765)        │    │
│  └─────────────────────────────────┘    │
└──────────────────────────────────────────┘
```

**核心原则**：
- 前端为纯静态资源，无 Node.js 运行时依赖
- API 地址通过 `--dart-define` 编译时注入，不同环境构建不同产物
- 静态资源启用长缓存（30 天），index.html 不缓存

---

## 二、环境配置要求

### 2.1 构建环境要求

| 工具          | 版本要求            | 说明                 |
| ----------- | --------------- | ------------------ |
| Flutter SDK | >= 3.24.0       | 与 pubspec.yaml 一致  |
| Dart SDK    | >= 3.4.0 <4.0.0 | Flutter 自带          |
| Node.js     | 不需要             | Flutter Web 无需 Node |

**构建机可选方案**：
- 方案 A：本地 Windows 开发机（当前已装 Flutter）
- 方案 B：服务器安装 Flutter SDK 直接构建（节省传输时间）
- 方案 C：CI/CD 流水线（GitHub Actions / 自建 GitLab Runner）

### 2.2 服务器环境要求

| 项目       | 要求                           | 当前状态 |
| -------- | ---------------------------- | ---- |
| Nginx    | 已安装并运行                       | ✅    |
| 部署目录     | `/opt/dianzi/frontend/web`   | 待创建  |
| 磁盘空间     | >= 100MB（构建产物约 20-40MB）      | 充足   |
| 后端服务     | 已运行并可访问                      | ✅    |

### 2.3 环境变量配置

Flutter Web 通过 `--dart-define` 在**编译时**注入环境变量，无需运行时配置文件。

| 变量名              | 开发环境值                          | 生产环境值                          |
| ---------------- | ------------------------------ | ------------------------------ |
| API_BASE_URL     | `http://127.0.0.1:8765/api`    | `http://124.221.108.59/api`    |

> **注意**：当前代码中 `kApiBaseUrl` 已改为通过 `String.fromEnvironment` 读取（见 [api_client.dart:13](file:///f:/treaFiles/Ideas/ideas/idea-app/frontend/lib/services/api_client.dart#L13)），✅ 已修复。开发环境默认值为 `http://127.0.0.1:8765/api`，生产环境通过 `--dart-define=API_BASE_URL=...` 注入。

---

## 三、部署前准备工作

### 3.1 代码检查

#### 3.1.1 重构 API 基础 URL（✅ 已完成）

将硬编码的 API 地址改为编译时注入：

```dart
// lib/services/api_client.dart
// 修改前：
const String kApiBaseUrl = 'http://127.0.0.1:8765/api';

// 修改后（已应用）：
const String kApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://127.0.0.1:8765/api',  // 开发环境默认值
);
```

#### 3.1.2 静态代码分析

```bash
cd frontend
flutter analyze                    # 静态分析，0 error 才能继续
flutter test                       # 单元测试
```

#### 3.1.3 代码检查清单

- [x] `flutter analyze` 无 error（0 error，2 warning 非阻塞）✅
- [x] `flutter test` 全部通过 ✅
- [x] API 地址已改为 `String.fromEnvironment` ✅
- [x] 无硬编码的 `127.0.0.1` 或 `localhost`（除默认值外）✅
- [ ] 无 `print()` 调试语句残留（用 `debugPrint` 替代或删除）
- [x] 敏感信息（如 API Key）未出现在前端代码中 ✅

### 3.2 构建优化

#### 3.2.1 构建命令

```bash
cd frontend

# 生产环境构建（Web 渲染器：默认用 canvaskit，性能优于 html）
flutter build web --release \
  --dart-define=API_BASE_URL=http://124.221.108.59/api \
  --base-href "/"

# 构建产物位于：build/web/
```

#### 3.2.2 构建参数说明

| 参数                          | 说明                                       |
| --------------------------- | ---------------------------------------- |
| `--release`                 | 发布模式，启用 tree-shaking 和压缩                |
| `--dart-define=API_BASE_URL=...` | 编译时注入生产 API 地址                         |
| `--base-href "/"`           | Web 根路径部署（部署在子路径需改为 `/app/`）          |

#### 3.2.3 渲染器选择

| 渲染器        | 适用场景            | 本项目选择 |
| ---------- | --------------- | ----- |
| `canvaskit`（默认） | 桌面浏览器，性能优先      | ✅ 采用  |
| `html`     | 移动端浏览器，首屏优先     | 不采用   |

如需强制指定：
```bash
flutter build web --release --web-renderer canvaskit
```

#### 3.2.4 构建产物优化清单

- [x] 启用 `--release` 模式 ✅
- [x] Tree-shaking 生效（main.dart.js = 2.9MB，字体削减 99%+）✅
- [x] 静态资源已自动 hash 命名（Flutter 默认启用）✅
- [x] index.html 引用正确的 base-href（`<base href="/">`）✅

### 3.3 构建产物验证

```bash
# 检查构建产物
ls -la build/web/
# 期望文件：
# - index.html
# - main.dart.js（主程序，通常 1-2MB）
# - flutter_bootstrap.js
# - assets/
# - icons/
# - favicon.png
# - manifest.json

# 检查 index.html 中的 base href
grep '<base' build/web/index.html
# 期望：<base href="/">

# 本地预览验证（可选）
cd build/web && python -m http.server 8080
# 浏览器访问 http://localhost:8080 确认页面加载
```

---

## 四、部署实施步骤

### 4.1 服务器环境准备

#### 4.1.1 创建部署目录

```bash
ssh ubuntu@124.221.108.59

# 创建前端部署目录
sudo mkdir -p /opt/dianzi/frontend/web
sudo chown -R ubuntu:ubuntu /opt/dianzi/frontend

# 创建备份目录（如未创建）
sudo mkdir -p /opt/dianzi/frontend/releases
sudo chown -R ubuntu:ubuntu /opt/dianzi/frontend/releases
```

#### 4.1.2 确认 Nginx 配置

当前 [nginx/dianzi.conf](file:///f:/treaFiles/Ideas/ideas/idea-app/nginx/dianzi.conf) 已配置好前端静态资源 serve：

```nginx
location / {
    root /opt/dianzi/frontend/web;
    index index.html;
    try_files $uri $uri/ /index.html;    # SPA 路由回退

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?|ttf)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

**关键点**：
- `try_files $uri $uri/ /index.html`：SPA 路由必需，确保刷新子路由不 404
- 静态资源 30 天长缓存，`immutable` 标记防止重复请求
- index.html 默认不缓存（Nginx 对 html 文件默认行为）

验证 Nginx 配置已生效：
```bash
# 检查软链
ls -la /etc/nginx/sites-enabled/dianzi.conf

# 测试配置语法
sudo nginx -t

# 重载配置（如修改过）
sudo nginx -s reload
```

### 4.2 构建产物传输

#### 4.2.1 本地打包

```powershell
# Windows PowerShell
cd f:\treaFiles\Ideas\ideas\idea-app\frontend

# 打包构建产物（排除不必要的文件）
tar -czf dianzi-web-build.tar.gz -C build/web .
```

#### 4.2.2 上传到服务器

```powershell
# 上传到服务器临时目录
scp dianzi-web-build.tar.gz ubuntu@124.221.108.59:/tmp/
```

### 4.3 静态资源部署

#### 4.3.1 版本化部署（推荐）

采用版本化部署，便于快速回滚：

```bash
ssh ubuntu@124.221.108.59

# 变量定义
VERSION="v1.0.0-$(date +%Y%m%d%H%M)"
RELEASE_DIR="/opt/dianzi/frontend/releases/$VERSION"

# 1. 创建版本目录并解压
mkdir -p $RELEASE_DIR
tar -xzf /tmp/dianzi-web-build.tar.gz -C $RELEASE_DIR

# 2. 备份当前版本（如已部署过）
if [ -L /opt/dianzi/frontend/web ]; then
    CURRENT=$(readlink /opt/dianzi/frontend/web)
    echo "当前版本：$CURRENT"
fi

# 3. 切换软链（原子操作，瞬间生效）
ln -sfn $RELEASE_DIR /opt/dianzi/frontend/web

# 4. 验证
ls -la /opt/dianzi/frontend/web/
cat /opt/dianzi/frontend/web/index.html | head -5

# 5. 清理临时文件
rm /tmp/dianzi-web-build.tar.gz
```

#### 4.3.2 直接覆盖部署（简单模式）

首次部署或快速验证时可用：

```bash
ssh ubuntu@124.221.108.59

# 直接解压到目标目录
rm -rf /opt/dianzi/frontend/web/*
tar -xzf /tmp/dianzi-web-build.tar.gz -C /opt/dianzi/frontend/web/

# 验证
ls -la /opt/dianzi/frontend/web/
```

### 4.4 服务配置

#### 4.4.1 Nginx 重载

```bash
# 测试配置
sudo nginx -t

# 重载（无需重启 Nginx，不影响其他站点）
sudo nginx -s reload
```

#### 4.4.2 权限设置

```bash
# 确保 Nginx（www-data 用户）可读
chmod -R 755 /opt/dianzi/frontend/
find /opt/dianzi/frontend/ -type d -exec chmod 755 {} \;
find /opt/dianzi/frontend/ -type f -exec chmod 644 {} \;
```

---

## 五、部署后验证流程

### 5.1 功能测试

#### 5.1.1 基础访问测试

```bash
# 1. 首页可访问
curl -I http://124.221.108.59/
# 期望：HTTP/1.1 200 OK
# 期望：Content-Type: text/html

# 2. index.html 内容正确
curl -s http://124.221.108.59/ | head -20
# 期望：包含 <base href="/">
# 期望：包含 flutter_bootstrap.js

# 3. 静态资源可访问
curl -I http://124.221.108.59/main.dart.js
# 期望：HTTP/1.1 200 OK
# 期望：Content-Encoding: gzip（如启用）

# 4. SPA 路由回退（关键！）
curl -I http://124.221.108.59/auth
curl -I http://124.221.108.59/explore
# 期望：HTTP/1.1 200 OK（不是 404）
```

#### 5.1.2 核心功能测试清单

在浏览器中访问 `http://124.221.108.59`，逐项验证：

| 测试项             | 操作                          | 期望结果                    |
| --------------- | --------------------------- | ----------------------- |
| 首页加载            | 访问根路径                       | 页面正常渲染，无白屏              |
| 注册流程            | 输入用户名密码注册                   | 注册成功，跳转主页               |
| 登录流程            | 输入已注册账号登录                   | 登录成功，token 存储           |
| 发布点子            | 输入内容并发布                     | 点子出现在 Vault             |
| 探索页             | 切换到探索 tab                   | 显示其他用户点子                |
| Fork 点子         | 点击他人点子 fork                 | 创建新点子，fork_count +1     |
| AI 演化           | 选择点子点击演化                    | 返回 3 个变体                |
| 路由刷新            | 在 /auth 页面按 F5 刷新           | 页面正常加载（不 404）           |
| 401 跳转          | token 过期后操作                 | 自动跳转登录页                 |

#### 5.1.3 API 联通性测试

```bash
# 确认前端能访问后端 API
curl -s http://124.221.108.59/api/ideas/explore | jq .
# 期望：返回 {"circles": [...], "has_more": false}

# 浏览器 F12 → Network 检查
# 1. API 请求无 CORS 错误
# 2. 请求 URL 为 http://124.221.108.59/api/...
# 3. Authorization header 正确携带
```

### 5.2 性能测试

#### 5.2.1 加载性能

| 指标               | 目标值         | 测量工具              |
| ---------------- | ----------- | ----------------- |
| 首屏加载时间（FCP）      | < 2s        | Chrome DevTools   |
| 完全加载时间           | < 5s        | Chrome DevTools   |
| main.dart.js 体积  | < 2MB（gzip） | `ls -lh`          |
| 静态资源缓存命中率        | > 90%       | Nginx 日志分析         |

```bash
# 检查构建产物体积
du -sh /opt/dianzi/frontend/web/
ls -lh /opt/dianzi/frontend/web/main.dart.js

# 启用 gzip 压缩（如 Nginx 未启用）
# 检查 nginx.conf 是否有：
# gzip on;
# gzip_types text/plain application/javascript text/css;
```

#### 5.2.2 并发性能

```bash
# 用 ab 或 wrk 压测静态资源
ab -n 1000 -c 50 http://124.221.108.59/
# 期望：QPS > 500，无失败请求
```

### 5.3 兼容性测试

#### 5.3.1 浏览器兼容性矩阵

| 浏览器              | 版本     | 测试结果 |
| ---------------- | ------ | ---- |
| Chrome           | 最新版    | 待测   |
| Firefox          | 最新版    | 待测   |
| Safari           | 最新版    | 待测   |
| Edge             | 最新版    | 待测   |
| Chrome (Android) | 最新版    | 待测   |
| Safari (iOS)     | 最新版    | 待测   |

> **注意**：Flutter Web (canvaskit) 在 IE 浏览器不支持，本项目不考虑 IE。

#### 5.3.2 移动端适配测试

| 测试项        | 期望                       |
| ---------- | ------------------------ |
| 手机竖屏显示     | 布局正常，无横向滚动               |
| 平板显示       | 布局自适应                    |
| 触摸操作       | 按钮点击区域足够大（>= 44pt）       |
| 输入法遮挡      | 输入框不被键盘遮挡                |

---

## 六、风险评估及应对策略

### 6.1 部署风险矩阵

| 风险项                  | 概率  | 影响  | 风险等级 | 应对策略                                   |
| -------------------- | --- | --- | ---- | -------------------------------------- |
| API 地址硬编码导致无法访问后端     | 高   | 高   | 🔴 高 | 部署前代码检查，改用 `--dart-define` 注入          |
| SPA 路由刷新 404         | 中   | 高   | 🟡 中 | Nginx 配置 `try_files ... /index.html`   |
| CORS 错误              | 中   | 高   | 🟡 中 | 后端 CORS_ORIGINS 已包含 IP，无需额外处理          |
| 构建产物体积过大             | 低   | 中   | 🟢 低 | 启用 release 模式，检查 tree-shaking          |
| canvaskit 加载慢        | 中   | 中   | 🟡 中 | canvaskit 由 CDN 加载，首次访问慢属正常            |
| 静态资源缓存导致更新不生效        | 中   | 中   | 🟡 中 | 静态文件 hash 命名 + index.html 不缓存          |
| Nginx 配置错误影响其他站点     | 低   | 高   | 🟡 中 | 修改前 `nginx -t` 测试，使用独立 server block    |
| 部署过程中服务中断            | 低   | 中   | 🟢 低 | 采用软链原子切换，用户无感知                        |

### 6.2 应急预案

#### 6.2.1 页面白屏

**排查步骤**：
1. F12 查看 Console 错误
2. 检查 `main.dart.js` 是否 404
3. 检查 `base href` 是否正确
4. 检查 API 地址是否可达

#### 6.2.2 API 请求失败

**排查步骤**：
1. F12 → Network 查看请求状态码
2. 确认请求 URL 是否为 `http://124.221.108.59/api/...`
3. 检查后端服务是否运行：`curl http://124.221.108.59/health`
4. 检查 CORS：后端 `CORS_ORIGINS` 是否包含 IP

#### 6.2.3 路由刷新 404

**原因**：Nginx 未配置 SPA 回退
**解决**：确认 `try_files $uri $uri/ /index.html;` 配置存在

---

## 七、持续部署策略（CI/CD）

### 7.1 CI/CD 流程设计

#### 7.1.1 流程图

```
开发者 push 代码
    │
    ▼
┌─────────────────┐
│ GitHub Actions  │  触发条件：push to main / tag v*
│  ├─ 代码检查      │  flutter analyze
│  ├─ 单元测试      │  flutter test
│  ├─ 构建产物      │  flutter build web --release
│  └─ 部署服务器    │  scp + ssh deploy
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 服务器            │
│  ├─ 版本化部署    │  /opt/dianzi/frontend/releases/vX.Y.Z
│  ├─ 软链切换      │  ln -sfn
│  └─ 健康检查      │  curl -I
└─────────────────┘
```

#### 7.1.2 GitHub Actions 配置示例

创建 `.github/workflows/deploy-web.yml`：

```yaml
name: Deploy Flutter Web

on:
  push:
    tags:
      - 'v*'    # 仅 tag 触发部署
  workflow_dispatch:    # 支持手动触发

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.24.0'

      - name: Install dependencies
        run: flutter pub get
        working-dir: frontend

      - name: Analyze
        run: flutter analyze
        working-dir: frontend

      - name: Test
        run: flutter test
        working-dir: frontend

      - name: Build Web
        run: |
          flutter build web --release \
            --dart-define=API_BASE_URL=${{ secrets.API_BASE_URL }} \
            --base-href "/"
        working-dir: frontend

      - name: Upload to server
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          source: "frontend/build/web/*"
          target: "/tmp/dianzi-web-deploy"

      - name: Deploy on server
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            VERSION="v${{ github.ref_name }}-$(date +%Y%m%d%H%M)"
            RELEASE_DIR="/opt/dianzi/frontend/releases/$VERSION"
            mkdir -p $RELEASE_DIR
            cp -r /tmp/dianzi-web-deploy/frontend/build/web/* $RELEASE_DIR/
            ln -sfn $RELEASE_DIR /opt/dianzi/frontend/web
            sudo nginx -s reload
            curl -sf http://127.0.0.1/ | grep -q "flutter_bootstrap.js" && echo "Deploy success" || echo "Deploy failed"
```

#### 7.1.3 所需 GitHub Secrets

| Secret 名            | 说明                           |
| -------------------- | ---------------------------- |
| `SERVER_HOST`        | 服务器 IP（124.221.108.59）       |
| `SERVER_USER`        | SSH 用户名（ubuntu）              |
| `SSH_PRIVATE_KEY`    | SSH 私钥（用于免密登录）               |
| `API_BASE_URL`       | 生产 API 地址（http://124.221.108.59/api） |

### 7.2 版本控制策略

#### 7.2.1 版本号规范

采用 [Semantic Versioning](https://semver.org/)：

```
v<MAJOR>.<MINOR>.<PATCH>
例：v1.0.0、v1.1.0、v1.1.1
```

| 版本类型   | 触发条件           | 示例            |
| ------ | -------------- | ------------- |
| MAJOR  | 不兼容的 API 变更    | v2.0.0        |
| MINOR  | 向下兼容的功能新增      | v1.1.0        |
| PATCH  | 向下兼容的 Bug 修复   | v1.0.1        |

#### 7.2.2 发布流程

```bash
# 1. 更新 pubspec.yaml 版本号
# version: 1.0.0 → 1.1.0

# 2. 提交代码
git add -A
git commit -m "release: v1.1.0"

# 3. 打 tag
git tag v1.1.0
git push origin v1.1.0

# 4. GitHub Actions 自动触发部署
```

#### 7.2.3 版本目录管理

```bash
# 服务器上的版本目录结构
/opt/dianzi/frontend/releases/
├── v1.0.0-202607091200/    # 历史版本
├── v1.0.1-202607091500/    # 历史版本
└── v1.1.0-202607101000/    # 当前版本（软链指向）

# 清理旧版本（保留最近 5 个）
ls -dt /opt/dianzi/frontend/releases/*/ | tail -n +6 | xargs rm -rf
```

### 7.3 回滚机制

#### 7.3.1 快速回滚（秒级）

利用软链切换实现秒级回滚：

```bash
# 查看所有版本
ls -lt /opt/dianzi/frontend/releases/

# 回滚到指定版本
ln -sfn /opt/dianzi/frontend/releases/v1.0.0-202607091200 /opt/dianzi/frontend/web
sudo nginx -s reload

# 验证
curl -s http://124.221.108.59/ | head -5
```

#### 7.3.2 回滚脚本

创建 `/opt/dianzi/frontend/rollback.sh`：

```bash
#!/bin/bash
# 用法：./rollback.sh [版本目录名]
# 不带参数则列出所有版本

RELEASES_DIR="/opt/dianzi/frontend/releases"
WEB_DIR="/opt/dianzi/frontend/web"

if [ -z "$1" ]; then
    echo "可用版本（按时间倒序）："
    ls -lt $RELEASES_DIR/ | grep '^d' | awk '{print $9}'
    echo ""
    CURRENT=$(readlink $WEB_DIR)
    echo "当前版本：$CURRENT"
    echo "用法：$0 <版本目录名>"
    exit 0
fi

TARGET="$RELEASES_DIR/$1"
if [ ! -d "$TARGET" ]; then
    echo "❌ 版本不存在：$1"
    exit 1
fi

ln -sfn $TARGET $WEB_DIR
sudo nginx -s reload

echo "✅ 已回滚到：$1"
curl -s http://127.0.0.1/ | head -5
```

#### 7.3.3 回滚触发条件

| 触发条件              | 回滚方式   | 预计耗时 |
| ----------------- | ------ | ---- |
| 部署后白屏             | 软链切回上版  | < 10s |
| 核心功能不可用           | 软链切回上版  | < 10s |
| 性能严重退化            | 软链切回上版  | < 10s |
| 代码回退后重新部署         | 重新构建+部署 | 5-10min |

---

## 八、部署执行清单

### 8.1 部署前检查清单

- [x] `flutter analyze` 无 error ✅
- [x] `flutter test` 全部通过 ✅
- [x] API 地址已改为 `String.fromEnvironment` ✅
- [x] 无硬编码敏感信息 ✅
- [x] 服务器 `/opt/dianzi/frontend/web` 目录就绪 ✅
- [x] Nginx 配置已包含前端 location ✅
- [x] 后端服务运行正常（`curl http://124.221.108.59/health`）✅

### 8.2 部署执行步骤

1. **本地构建**
   ```bash
   cd frontend
   flutter build web --release \
     --dart-define=API_BASE_URL=http://124.221.108.59/api \
     --base-href "/"
   ```

2. **打包上传**
   ```powershell
   tar -czf dianzi-web-build.tar.gz -C build/web .
   scp dianzi-web-build.tar.gz ubuntu@124.221.108.59:/tmp/
   ```

3. **服务器部署**
   ```bash
   ssh ubuntu@124.221.108.59
   VERSION="v1.0.0-$(date +%Y%m%d%H%M)"
   RELEASE_DIR="/opt/dianzi/frontend/releases/$VERSION"
   mkdir -p $RELEASE_DIR
   tar -xzf /tmp/dianzi-web-build.tar.gz -C $RELEASE_DIR
   ln -sfn $RELEASE_DIR /opt/dianzi/frontend/web
   sudo nginx -s reload
   rm /tmp/dianzi-web-build.tar.gz
   ```

4. **验证**
   ```bash
   curl -I http://124.221.108.59/
   curl -s http://124.221.108.59/api/ideas/explore | jq .
   ```

### 8.3 部署后验证清单

- [x] 首页可访问（HTTP 200）✅
- [x] 静态资源可访问（main.dart.js 200/3046983bytes、flutter_bootstrap.js）✅
- [x] SPA 路由刷新不 404（/auth 返回 200）✅
- [x] API 请求成功（探索页返回 12 个点子）✅
- [ ] 注册/登录功能正常（需浏览器手动验证）
- [ ] 发布点子功能正常（需浏览器手动验证）
- [ ] AI 演化功能正常（需浏览器手动验证）
- [ ] 移动端适配正常（需浏览器手动验证）

---

## 九、附录

### 附录 A：常用运维命令

```bash
# 查看当前部署版本
readlink /opt/dianzi/frontend/web

# 查看所有历史版本
ls -lt /opt/dianzi/frontend/releases/

# 查看 Nginx 访问日志
sudo tail -f /var/log/nginx/dianzi_access.log

# 查看 Nginx 错误日志
sudo tail -f /var/log/nginx/dianzi_error.log

# 重载 Nginx 配置
sudo nginx -s reload

# 清理旧版本（保留最近 5 个）
ls -dt /opt/dianzi/frontend/releases/*/ | tail -n +6 | xargs rm -rf
```

### 附录 B：本地开发环境配置

```bash
# 开发模式运行（默认连接本地后端）
cd frontend
flutter run -d chrome

# 指定 API 地址运行
flutter run -d chrome \
  --dart-define=API_BASE_URL=http://124.221.108.59/api
```

### 附录 C：文件清单

部署完成后服务器目录结构：

```
/opt/dianzi/frontend/
├── web/                        → 软链指向当前版本
├── releases/
│   └── v1.0.0-202607092045/    ← 当前版本
│       ├── index.html
│       ├── main.dart.js        (2.9MB)
│       ├── flutter_bootstrap.js
│       ├── flutter.js
│       ├── flutter_service_worker.js
│       ├── canvaskit/
│       ├── assets/
│       ├── icons/
│       ├── favicon.png
│       ├── manifest.json
│       └── version.json
└── rollback.sh
```

---

## 十、实际部署结果（v1.1 补充）

### 10.1 部署完成状态

| 步骤              | 状态 | 说明                                    |
| --------------- | -- | ------------------------------------- |
| 修复 API 硬编码      | ✅ | `kApiBaseUrl` 改为 `String.fromEnvironment` |
| 代码检查            | ✅ | `flutter analyze` 0 error，`flutter test` 通过 |
| 构建产物            | ✅ | `main.dart.js` 2.9MB，字体 tree-shaking 99%+ |
| 服务器部署           | ✅ | 版本 `v1.0.0-202607092045`，软链切换成功       |
| 部署验证            | ✅ | 7 项验证全部通过                             |
| CI/CD 配置        | ✅ | `.github/workflows/deploy-web.yml` 已创建 |

### 10.2 实际构建参数

```bash
flutter build web --release \
  --dart-define=API_BASE_URL=http://124.221.108.59/api \
  --base-href "/"
```

### 10.3 构建产物信息

| 文件                    | 大小       | 说明           |
| --------------------- | -------- | ------------ |
| main.dart.js          | 2.9MB    | 主程序（gzip 后约 700KB） |
| flutter_bootstrap.js  | 9.9KB    | 引导脚本         |
| flutter.js            | 9.5KB    | Flutter 加载器 |
| index.html            | 1.5KB    | 入口页面         |
| 打包后 tar.gz           | 13.6MB   | 含 canvaskit  |

字体 tree-shaking 效果：
- CupertinoIcons.ttf：257KB → 1.4KB（99.4% 削减）
- MaterialIcons-Regular.otf：1.6MB → 11KB（99.3% 削减）

### 10.4 部署验证结果

| 验证项        | 结果 | 关键证据                                       |
| ---------- | -- | ------------------------------------------ |
| 版本软链       | ✅ | `/opt/dianzi/frontend/releases/v1.0.0-202607092045` |
| index.html | ✅ | `<!DOCTYPE html>` + `<base href="/">`      |
| 目录结构       | ✅ | 14 个文件/目录齐全                                |
| HTTP 状态    | ✅ | `200 OK`，`Content-Type: text/html`         |
| SPA 路由回退   | ✅ | `/auth` 返回 `200`（不是 404）                   |
| API 联通性    | ✅ | 返回 12 个点子的 JSON 数据                         |
| main.dart.js | ✅ | `200`，`3046983 bytes`                      |

### 10.5 代码修改记录

| 文件                     | 修改内容                                     |
| ---------------------- | ---------------------------------------- |
| `lib/services/api_client.dart` | `kApiBaseUrl` 从硬编码改为 `String.fromEnvironment`，支持 `--dart-define` 注入 |
| `.github/workflows/deploy-web.yml` | 新建 GitHub Actions CI/CD 配置，tag 触发自动构建部署 |

### 10.6 CI/CD 配置说明

已创建 [.github/workflows/deploy-web.yml](file:///f:/treaFiles/Ideas/ideas/idea-app/.github/workflows/deploy-web.yml)，启用步骤：

1. 初始化 Git 并推送到 GitHub
2. 配置 GitHub Secrets：
   - `SERVER_HOST`：`124.221.108.59`
   - `SERVER_USER`：`ubuntu`
   - `SSH_PRIVATE_KEY`：SSH 私钥内容
   - `API_BASE_URL`：`http://124.221.108.59/api`
3. 配置服务器 SSH 免密登录
4. 打 tag 触发：`git tag v1.0.1 && git push origin v1.0.1`

### 10.7 常见问题排查

| 问题               | 排查方法                                              | 解决方案                    |
| ---------------- | ------------------------------------------------- | ----------------------- |
| 页面白屏             | F12 → Console 查看错误                                | 检查 main.dart.js 是否 404  |
| API 请求失败         | F12 → Network 查看请求状态码                             | 确认 API URL 正确、后端运行     |
| 路由刷新 404         | `curl -I http://124.221.108.59/auth`              | 检查 Nginx try_files 配置  |
| 静态资源 403        | `ls -la /opt/dianzi/frontend/web/`                | 检查文件权限（755/644）       |
| 构建产物体积过大        | `ls -lh build/web/main.dart.js`                   | 确认 --release 模式        |
| CORS 错误          | F12 → Console                                     | 后端 CORS_ORIGINS 已包含 IP |

### 10.8 回滚操作

```bash
# 查看所有版本
ls -lt /opt/dianzi/frontend/releases/

# 回滚到指定版本
ln -sfn /opt/dianzi/frontend/releases/v1.0.0-202607092045 /opt/dianzi/frontend/web
sudo nginx -s reload

# 验证
curl -I http://127.0.0.1/
```

---

**文档编制**：AI 助手
**编制日期**：2026-07-09
**下次评审**：下次版本发布时
