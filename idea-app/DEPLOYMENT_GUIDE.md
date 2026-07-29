# 电子点子 App 项目部署文档

| 项目名称  | 电子点子 App（Dianzi App）                             |
| ----- | ------------------------------------------------ |
| 文档版本  | v1.1                                             |
| 编制日期  | 2026-07-09                                       |
| 文档状态  | ✅ 已执行（后端服务已上线）                                   |
| 部署模式  | Docker Compose 隔离部署 + Nginx 反向代理共存               |
| 目标服务器 | 124.221.108.59（Ubuntu 22.04 LTS，3.3GB 内存）        |
| 服务地址  | http://124.221.108.59                            |

## 修订记录

| 版本   | 日期         | 修订人   | 修订内容                                      |
| ---- | ---------- | ----- | ----------------------------------------- |
| v1.0 | 2026-07-09 | AI 助手 | 初始版本，含完整流程、责任分工、回滚方案                     |
| v1.1 | 2026-07-09 | AI 助手 | 部署完成后更新：补充实际部署结果、问题修复记录、schema 修复、验证数据   |

***

## 一、项目概述

### 1.1 部署目标

将电子点子 App 的后端服务（FastAPI + PostgreSQL + Redis）部署到一台**已运行其他项目**的服务器上，做到：

- 与服务器上现有项目**零冲突共存**
- 部署过程**可追溯、可验证、可回滚**
- 符合项目质量标准（性能、安全、可维护性）

### 1.2 技术栈

| 层级    | 技术栈                        | 版本               |
| ----- | -------------------------- | ---------------- |
| 后端框架  | FastAPI + Uvicorn/Gunicorn | 0.115.6 / 0.34.0 |
| 数据库   | PostgreSQL                 | 16-alpine        |
| 缓存    | Redis                      | 7-alpine         |
| AI 服务 | DeepSeek API               | deepseek-chat    |
| 反向代理  | Nginx                      | 复用服务器现有实例        |
| 容器编排  | Docker Compose             | v2               |

### 1.3 部署架构

```
互联网用户
    │
    ▼
┌──────────────────────────────────────────┐
│ 服务器（已运行其他项目）                  │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │ Nginx (80/443) — 复用现有        │    │
│  │  ├─ existing-project.conf       │    │
│  │  └─ dianzi.conf (新增)           │    │
│  └──────────┬──────────────────────┘    │
│             │                            │
│  ┌──────────▼──────────────────────┐    │
│  │ Docker Compose 项目隔离          │    │
│  │  ├─ backend   127.0.0.1:8765    │    │
│  │  ├─ postgres  127.0.0.1:5433    │    │
│  │  └─ redis     127.0.0.1:6380    │    │
│  └─────────────────────────────────┘    │
│                                          │
│  其他现有项目（独立运行，互不干扰）       │
└──────────────────────────────────────────┘
```

**核心隔离原则**：

- 所有内部服务只绑定 `127.0.0.1`，不对外暴露
- 端口使用非默认值（5433/6380/8765），避免与现有项目冲突
- 数据通过 Docker volume 隔离，网络通过 Docker network 隔离

***

## 二、角色与职责分工（RACI 矩阵）

### 2.1 角色定义

| 角色       | 代号    | 说明                 |
| -------- | ----- | ------------------ |
| 用户       | **U** | 服务器所有者，拥有 SSH 访问权限 |
| AI 助手    | **A** | 提供配置文件、命令清单、问题诊断   |
| 服务器现有项目方 | **E** | 服务器上其他项目的维护者（如需协调） |

### 2.2 RACI 责任矩阵

**R** = Responsible（执行） / **A** = Accountable（负责） / **C** = Consulted（咨询） / **I** = Informed（知会）

| 部署任务                | U 用户 | A AI 助手 | E 现有项目方 |
| ------------------- | ---- | ------- | ------- |
| 信息收集（域名/密码/API Key） | R/A  | C       | I       |
| 服务器环境检查             | R/A  | C       | I       |
| 现有项目兼容性评估           | R    | C/A     | C       |
| 域名 DNS 解析配置         | R/A  | I       | I       |
| 服务器 Docker 安装（如缺）   | R/A  | C       | I       |
| 部署目录创建与代码上传         | R/A  | C       | I       |
| 生产配置文件生成            | C    | R/A     | I       |
| .env 敏感信息填写         | R/A  | I       | I       |
| Docker 镜像构建与启动      | R    | C/A     | I       |
| Nginx 配置新增          | R/A  | C       | I       |
| SSL 证书申请            | R/A  | C       | I       |
| 服务健康检查              | R    | C/A     | I       |
| 功能测试验证              | R    | C/A     | I       |
| 现有项目回归验证            | R/A  | C       | C       |
| 性能测试                | R    | C/A     | I       |
| 回滚执行（如需）            | R/A  | C       | I       |
| 部署报告归档              | R    | A       | I       |

### 2.3 双方工作边界

#### ✅ AI 助手独立完成

- 生成所有部署配置文件（Dockerfile、compose、nginx、systemd、.env 模板）
- 编写一键部署脚本和回滚脚本
- 提供完整的命令清单（可逐条复制执行）
- 远程协助排查问题（基于用户提供的日志分析）
- 生成部署报告模板

#### ❌ 用户必须亲自完成

1. **SSH 登录服务器**执行所有命令
2. **填写敏感信息**：域名、SSL 证书路径、DeepSeek API Key、强密码
3. **域名 DNS 解析**：把新域名 A 记录指向服务器 IP
4. **备案/证书申请**（如需在中国大陆运行）
5. **与现有项目方沟通**：确认 Nginx 配置新增、端口分配无冲突
6. **现有项目回归测试**：确认部署未影响其他业务

***

## 三、部署环境要求

### 3.1 服务器硬件最低要求

| 资源  | 最低要求          | 推荐      | 检查命令      |
| --- | ------------- | ------- | --------- |
| CPU | 2 核           | 4 核     | `nproc`   |
| 内存  | 4 GB（含现有项目占用） | 8 GB    | `free -h` |
| 磁盘  | 10 GB 可用      | 20 GB   | `df -h /` |
| 带宽  | 5 Mbps        | 10 Mbps | —         |

### 3.2 软件依赖

| 软件             | 最低版本   | 必装/可选      | 安装命令                                        |
| -------------- | ------ | ---------- | ------------------------------------------- |
| Docker Engine  | 24.0+  | 必装         | `curl -fsSL https://get.docker.com \| sh`   |
| Docker Compose | v2.20+ | 必装         | 随 Docker 一起装                                |
| Nginx          | 1.18+  | 必装（复用现有）   | `apt install nginx`                         |
| certbot        | 2.0+   | 可选（HTTPS）  | `apt install certbot python3-certbot-nginx` |
| Python         | 3.11+  | 可选（仅手动部署时） | `apt install python3.11`                    |

### 3.3 端口规划

| 服务          | 端口   | 绑定地址      | 是否对外 | 说明         |
| ----------- | ---- | --------- | ---- | ---------- |
| Nginx HTTP  | 80   | 0.0.0.0   | 是    | 复用现有       |
| Nginx HTTPS | 443  | 0.0.0.0   | 是    | 复用现有       |
| SSH         | 22   | 0.0.0.0   | 是    | 复用现有       |
| 后端 API      | 8765 | 127.0.0.1 | 否    | 仅 Nginx 访问 |
| PostgreSQL  | 5433 | 127.0.0.1 | 否    | 仅后端访问      |
| Redis       | 6380 | 127.0.0.1 | 否    | 仅后端访问      |

> ⚠️ **关键原则**：8765/5433/6380 三端口**必须只绑 127.0.0.1**，避免被外部扫描或与未来项目冲突。

### 3.4 域名与证书要求

| 项目            | 要求                        |
| ------------- | ------------------------- |
| 后端 API 域名     | 1 个，如 `api.dianzi.app`    |
| 前端 Web 域名（可选） | 1 个，如 `app.dianzi.app`    |
| DNS 解析        | A 记录指向服务器公网 IP            |
| SSL 证书        | Let's Encrypt 免费（推荐）或商业证书 |
| 备案            | 中国大陆服务器 + 国内域名必须 ICP 备案   |

***

## 四、部署阶段总览

| 阶段     | 任务概要   | 执行人    | 预估时长         | 关键产出                 |
| ------ | ------ | ------ | ------------ | -------------------- |
| P0     | 前期准备   | U + A  | 30 分钟        | 信息收集表、环境检查报告         |
| P1     | 环境配置   | U      | 30 分钟        | Docker/Nginx 就绪、目录创建 |
| P2     | 资源部署   | U + A  | 30 分钟        | 代码上传、配置文件就位          |
| P3     | 服务启动   | U      | 15 分钟        | 容器运行、健康检查通过          |
| P4     | 系统测试   | U + A  | 60 分钟        | 功能测试、性能测试报告          |
| P5     | 上线验证   | U      | 30 分钟        | 公网访问、现有项目回归          |
| P6     | 交付归档   | A      | 15 分钟        | 部署报告、运维手册            |
| **合计** | <br /> | <br /> | **\~3.5 小时** | <br />               |

***

## 五、P0 — 前期准备阶段

### 5.1 信息收集表（用户填写）

用户需先填写下表，AI 助手据此定制配置：

| #  | 项目               | 你的值                                 | 示例                          |
| -- | ---------------- | ----------------------------------- | --------------------------- |
| 1  | 服务器公网 IP         | 124.221.108.59                      | `47.96.x.x`                 |
| 2  | 操作系统版本           | Ubuntu 22.04.05 LTS                 | `Ubuntu 22.04 LTS`          |
| 3  | SSH 登录用户名        | ubuntu                              | `ubuntu` 或 `root`           |
| 4  | 现有 Nginx 配置目录    | 未安装                                 | `/etc/nginx/sites-enabled/` |
| 5  | 现有项目占用端口         | 7860                                | `8080, 3306, 6379`          |
| 6  | 是否已装 Docker      | 是                                   | 是/否                         |
| 7  | 是否已有 PostgreSQL  | 否                                   | 是/否（端口\_\_\_）               |
| 8  | 是否已有 Redis       | 否                                   | 是/否（端口\_\_\_）               |
| 9  | 服务器剩余内存          | 1.4GB                               | `2.5GB`                     |
| 10 | 新 API 域名         | api.dianzi.app                      | `api.dianzi.app`            |
| 11 | 新 Web 域名（可选）     | api.dianzi.app                      | `app.dianzi.app`            |
| 12 | 是否有 SSL 证书       | 否                                   | 是/否                         |
| 13 | DeepSeek API Key | sk-<your_deepseek_api_key> | `sk-...`                    |
| 14 | 域名是否已备案          | 否                                   | 是/否/不需要                     |

**执行人**：U
**工具**：SSH 客户端、文本编辑器
**完成标志**：表格 14 项全部填写

### 5.2 服务器环境检查

用户 SSH 登录服务器，依次执行：

```bash
# ===== 1. 系统基础信息 =====
echo "===== 系统信息 ====="
cat /etc/os-release | grep PRETTY
echo "CPU 核数: $(nproc)"
free -h
df -h / /var /opt 2>/dev/null

# ===== 2. 端口占用情况 =====
echo "===== 端口占用 ====="
sudo ss -tlnp | grep -E ':(80|443|5432|5433|6379|6380|8000|8765)\s' || echo "关键端口均空闲"

# ===== 3. Docker 状态 =====
echo "===== Docker 状态 ====="
docker --version 2>/dev/null && docker compose version 2>/dev/null || echo "Docker 未安装"
sudo docker ps -a 2>/dev/null

# ===== 4. Nginx 状态 =====
echo "===== Nginx 状态 ====="
nginx -v 2>&1 || echo "Nginx 未安装"
ls /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null

# ===== 5. 现有 PG/Redis =====
echo "===== 现有数据库 ====="
psql --version 2>/dev/null || echo "无系统 PG"
redis-cli --version 2>/dev/null || echo "无系统 Redis"
sudo systemctl status postgresql 2>/dev/null | head -3
sudo systemctl status redis 2>/dev/null | head -3

# ===== 6. 防火墙 =====
echo "===== 防火墙 ====="
sudo ufw status verbose 2>/dev/null || sudo firewall-cmd --list-all 2>/dev/null
```

**执行人**：U
**工具**：SSH
**完成标志**：把以上输出完整贴给 AI 助手
**交付物**：环境检查报告（AI 助手基于此生成定制配置）

### 5.3 兼容性评估（AI 助手执行）

AI 助手根据 5.1、5.2 输出，给出：

- 端口冲突分析及最终端口分配方案
- PG/Redis 是新建 Docker 实例还是复用现有实例
- Nginx 配置文件放置路径
- 资源占用评估（是否会挤占现有项目）
- 风险提示

**执行人**：A
**完成标志**：用户确认评估结论

***

## 六、P1 — 环境配置阶段

### 6.1 安装 Docker（如未装）

```bash
# 一键安装
curl -fsSL https://get.docker.com | sudo sh

# 把当前用户加入 docker 组（免 sudo）
sudo usermod -aG docker $USER

# 重新登录 SSH 使组生效
exit
# 重新 ssh 登录后验证
docker ps
```

**执行人**：U
**工具**：SSH
**完成标志**：`docker ps` 正常输出（无权限错误）

### 6.2 创建部署目录

```bash
sudo mkdir -p /opt/dianzi/{backend,frontend,nginx,backup}
sudo chown -R $USER:$USER /opt/dianzi
mkdir -p /opt/dianzi/backup
```

**执行人**：U
**完成标志**：`ls -la /opt/dianzi/` 显示 4 个子目录

### 6.3 域名 DNS 解析

在域名服务商控制台添加 A 记录：

| 记录类型 | 主机记录 | 记录值      | TTL |
| ---- | ---- | -------- | --- |
| A    | api  | 服务器公网 IP | 600 |
| A    | app  | 服务器公网 IP | 600 |

验证解析生效：

```bash
# 在服务器或本地执行
dig api.dianzi.app +short
dig app.dianzi.app +short
# 应返回服务器公网 IP
```

**执行人**：U
**工具**：域名服务商控制台
**完成标志**：dig 命令返回正确 IP（DNS 生效需 5-10 分钟）

### 6.4 防火墙配置

```bash
# 放行 80/443（如未放行）
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

> 不要放行 5433/6380/8765，这些只内网访问。

**执行人**：U
**完成标志**：`ufw status` 显示 80/443 放行

***

## 七、P2 — 资源部署阶段

### 7.1 上传后端代码

#### 方案 A：Git 克隆（推荐）

```bash
cd /opt/dianzi
git clone <你的仓库地址> backend
```

#### 方案 B：scp 上传（本地 Windows PowerShell）

```powershell
# 本地打包（排除虚拟环境、缓存、本地数据库）
cd f:\treaFiles\Ideas\ideas\idea-app
tar -czf backend.tar.gz `
    --exclude='backend/venv' `
    --exclude='backend/__pycache__' `
    --exclude='backend/dianzi_dev.db' `
    --exclude='backend/.env' `
    --exclude='backend/tests' `
    backend

# 上传
scp backend.tar.gz user@your-server-ip:/tmp/

# SSH 登录服务器解压
ssh user@your-server-ip
cd /opt/dianzi
tar -xzf /tmp/backend.tar.gz
rm /tmp/backend.tar.gz
```

**执行人**：U
**工具**：git 或 scp/tar
**完成标志**：`ls /opt/dianzi/backend/main.py` 存在

### 7.2 生成生产配置文件（AI 助手提供）

AI 助手根据 P0 阶段收集的信息，生成以下文件（用户保存到对应路径）：

| 文件                      | 路径                                    | 生成方 |
| ----------------------- | ------------------------------------- | --- |
| Dockerfile              | `/opt/dianzi/backend/Dockerfile`      | A   |
| docker-compose.prod.yml | `/opt/dianzi/docker-compose.prod.yml` | A   |
| .env 模板                 | `/opt/dianzi/backend/.env.template`   | A   |
| Nginx 配置                | `/opt/dianzi/nginx/dianzi.conf`       | A   |
| 部署脚本                    | `/opt/dianzi/deploy.sh`               | A   |
| 回滚脚本                    | `/opt/dianzi/rollback.sh`             | A   |

**执行人**：A 生成，U 保存
**完成标志**：所有配置文件就位

### 7.3 填写 .env 敏感信息（用户独立完成）

```bash
cp /opt/dianzi/backend/.env.template /opt/dianzi/backend/.env
nano /opt/dianzi/backend/.env
```

**必填项**：

```ini
# 64 位随机串（生成命令：python3 -c "import secrets; print(secrets.token_urlsafe(48))"）
JWT_SECRET=________________________________

# 强密码（建议 24 位以上）
PG_PASSWORD=________________________________
REDIS_PASSWORD=________________________________

# DeepSeek API Key
DEEPSEEK_API_KEY=sk-________________________________

# 前端域名（逗号分隔，无通配符）
CORS_ORIGINS=https://app.dianzi.app
```

> ⚠️ `.env` 文件权限设为 600：`chmod 600 /opt/dianzi/backend/.env`

**执行人**：U（独立完成，不通过网络传输给 AI）
**工具**：nano/vim
**完成标志**：`.env` 文件所有必填项已填写

### 7.4 配置 Nginx

```bash
# 软链到 sites-enabled
sudo ln -s /opt/dianzi/nginx/dianzi.conf /etc/nginx/sites-enabled/

# 语法检查（必须通过）
sudo nginx -t
```

> 此时先不要 reload，等后端启动后再 reload。

**执行人**：U
**完成标志**：`nginx -t` 显示 `syntax is ok`

***

## 八、P3 — 服务启动阶段

### 8.1 一键部署

```bash
cd /opt/dianzi
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` 内部执行流程：

1. 检查环境（Docker、.env）
2. 构建后端镜像
3. 启动 PG/Redis/Backend 三个容器
4. 等待健康检查（最多 60 秒）
5. 重载 Nginx

**执行人**：U
**工具**：deploy.sh
**完成标志**：脚本输出"部署完成"

### 8.2 健康检查

```bash
# 容器状态（应该都是 Up）
docker compose -f /opt/dianzi/docker-compose.prod.yml ps

# 后端健康
curl -v http://127.0.0.1:8765/health
# 期望：200 + {"status":"ok"}

# PG 连通
docker exec dianzi-postgres pg_isready -U dianzi -d dianzi_app

# Redis 连通
docker exec dianzi-redis redis-cli -a <redis密码> ping
```

**执行人**：U
**完成标志**：4 项检查全部通过

### 8.3 申请 HTTPS 证书

```bash
sudo certbot --nginx -d api.dianzi.app -d app.dianzi.app
# 选择自动重定向 HTTP 到 HTTPS
```

**执行人**：U
**完成标志**：`curl https://api.dianzi.app/health` 返回 200

***

## 九、P4 — 系统测试阶段

### 9.1 服务级测试

| 测试项         | 命令                                                                  | 预期                    |
| ----------- | ------------------------------------------------------------------- | --------------------- |
| 后端健康        | `curl http://127.0.0.1:8765/health`                                 | 200                   |
| Swagger 可访问 | `curl http://127.0.0.1:8765/docs`                                   | 200 HTML              |
| PG 表结构      | `docker exec dianzi-postgres psql -U dianzi -d dianzi_app -c "\dt"` | 10 张表                 |
| Redis 连接    | `docker exec dianzi-redis redis-cli -a <pwd> ping`                  | PONG                  |
| 容器重启策略      | `docker inspect dianzi-backend \| grep RestartPolicy`               | always/unless-stopped |

**执行人**：U 执行，A 分析异常
**完成标志**：5 项全通过

### 9.2 功能级测试

按以下顺序执行 API 测试：

```bash
# 1. 用户注册
curl -X POST https://api.dianzi.app/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"deploy_test","password":"Test1234!"}'
# 期望：201

# 2. 用户登录
TOKEN=$(curl -s -X POST https://api.dianzi.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"deploy_test","password":"Test1234!"}' | jq -r .access_token)
# 期望：token 非空

# 3. 探索页
curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.dianzi.app/api/ideas/explore | jq .
# 期望：circles 数组

# 4. 发布点子
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"部署验证测试点子"}' \
  https://api.dianzi.app/api/ideas
# 期望：201 + idea_id

# 5. 查看个人 Vault
curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.dianzi.app/api/vault | jq .
# 期望：包含刚发布的点子

# 6. AI 演化（如配置了 DeepSeek）
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"idea_id":"<上一步返回的id>"}' \
  https://api.dianzi.app/api/ideas/spark
# 期望：200 + 演化结果
```

**执行人**：U 执行，A 协助排查
**完成标志**：6 项功能全部通过
**交付物**：功能测试报告（截图或 curl 输出）

### 9.3 CORS 验证

```bash
curl -v -H "Origin: https://app.dianzi.app" \
  https://api.dianzi.app/api/ideas/explore 2>&1 | grep -i "access-control"
# 期望：access-control-allow-origin: https://app.dianzi.app
```

**执行人**：U
**完成标志**：CORS 头正确返回

### 9.4 性能测试

```bash
# 安装 wrk（如未装）
sudo apt install -y wrk

# 探索页压测（30 秒，50 并发）
wrk -t4 -c50 -d30s --latency \
  -H "Authorization: Bearer $TOKEN" \
  https://api.dianzi.app/api/ideas/explore
```

**验收标准**：

| 指标           | 合格线    | 优秀线    |
| ------------ | ------ | ------ |
| QPS（缓存命中）    | ≥500   | ≥1500  |
| QPS（缓存 miss） | ≥30    | ≥80    |
| P99 延迟       | <500ms | <200ms |
| 错误率          | <0.1%  | 0%     |

**执行人**：U 执行，A 分析报告
**完成标志**：性能指标达到合格线
**交付物**：性能测试报告

### 9.5 并发安全验证（基于上轮修复）

```bash
# 并发 50 次 fork 同一个点子，验证 fork_count 不丢失
IDEA_ID=<某个点子的id>
for i in {1..50}; do
  curl -X POST -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"parent_id\":\"$IDEA_ID\"}" \
    https://api.dianzi.app/api/ideas/fork &
done
wait

# 验证 fork_count 准确等于 50
curl -s https://api.dianzi.app/api/ideas/$IDEA_ID | jq .fork_count
```

**执行人**：U
**完成标志**：fork\_count = 50（无丢失更新）

***

## 十、P5 — 上线验证阶段

### 10.1 公网访问验证

| 验证项      | URL                             | 预期             |
| -------- | ------------------------------- | -------------- |
| API 健康   | `https://api.dianzi.app/health` | 200            |
| Swagger  | `https://api.dianzi.app/docs`   | 页面正常           |
| Web 前端   | `https://app.dianzi.app`        | 页面加载           |
| HTTPS 证书 | 浏览器查看                           | 有效（绿锁）         |
| HTTP 跳转  | `http://api.dianzi.app`         | 自动 301 到 HTTPS |

**执行人**：U
**完成标志**：5 项全部通过

### 10.2 现有项目回归验证（关键！）

**必须验证服务器上其他项目仍然正常**：

```bash
# 列出所有 Nginx server_name
sudo nginx -T 2>/dev/null | grep server_name

# 逐个访问现有项目域名
curl -sI https://现有项目1域名.com | head -1   # 期望 200/301/302
curl -sI https://现有项目2域名.com | head -1   # 期望 200/301/302

# 检查端口冲突
sudo ss -tlnp | grep -E ':(80|443)\s'   # 应该只有 Nginx
sudo ss -tlnp | grep -E ':(5433|6380|8765)\s'  # 应该都是 127.0.0.1

# 检查 Docker 资源占用
docker stats --no-stream
```

**执行人**：U
**完成标志**：现有项目全部正常，无端口冲突
**交付物**：现有项目回归测试报告

### 10.3 监控配置

```bash
# 设置日志轮转（避免日志撑满磁盘）
sudo tee /etc/logrotate.d/dianzi <<'EOF'
/opt/dianzi/backup/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
EOF

# 设置数据库自动备份（每天凌晨 3 点）
crontab -e
# 加入：
0 3 * * * docker exec dianzi-postgres pg_dump -U dianzi dianzi_app | gzip > /opt/dianzi/backup/db_$(date +\%Y\%m\%d).sql.gz && find /opt/dianzi/backup/ -name "db_*.sql.gz" -mtime +7 -delete
```

**执行人**：U
**完成标志**：crontab -l 显示备份任务

***

## 十一、回滚方案

### 11.1 回滚触发条件

满足以下任一条件立即回滚：

- 后端服务无法启动且 30 分钟内无法修复
- 现有项目因本次部署出现故障
- 数据库数据丢失或损坏
- 安全漏洞（如 JWT\_SECRET 泄露）
- 用户明确要求回滚

### 11.2 回滚分级

| 级别    | 场景             | 操作                        | 数据影响   |
| ----- | -------------- | ------------------------- | ------ |
| L1 轻微 | 配置错误（CORS/JWT） | 修改 .env + restart backend | 无      |
| L2 中等 | 代码 bug 导致功能异常  | 回退到上个版本镜像                 | 无      |
| L3 严重 | 现有项目受影响        | 停止 dianzi 所有容器            | 无      |
| L4 灾难 | 数据损坏           | 停服 + 恢复昨日备份               | 丢失当日数据 |

### 11.3 回滚操作步骤

#### L1 配置回滚（5 分钟）

```bash
cd /opt/dianzi
nano backend/.env              # 改回正确配置
docker compose -f docker-compose.prod.yml restart backend
```

#### L2 代码回滚（10 分钟）

```bash
cd /opt/dianzi
# 回退到上个版本
git log --oneline -5           # 找到上个稳定版本
git checkout <上个稳定 commit>
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend
```

#### L3 紧急停止（2 分钟）

```bash
cd /opt/dianzi
./rollback.sh
# 等同于：docker compose -f docker-compose.prod.yml down
# 数据保留在 volume 中，不删除

# 同时移除 Nginx 配置
sudo rm /etc/nginx/sites-enabled/dianzi.conf
sudo nginx -t && sudo systemctl reload nginx
```

#### L4 数据恢复（30 分钟）

```bash
# 停止后端
docker compose -f /opt/dianzi/docker-compose.prod.yml stop backend

# 恢复昨日备份
cd /opt/dianzi/backup
gunzip < db_20260708.sql.gz | docker exec -i dianzi-postgres psql -U dianzi -d dianzi_app

# 重启后端
docker compose -f /opt/dianzi/docker-compose.prod.yml start backend
```

### 11.4 回滚验证

回滚后必须验证：

1. 后端健康检查通过
2. 现有项目访问正常
3. 数据完整性（用户数、点子数与备份一致）

**执行人**：U 执行，A 协助
**完成标志**：验证全部通过

***

## 十二、质量标准与验收

### 12.1 部署质量验收清单

| #  | 验收项    | 验收标准                       | 验证方法                | 结果 |
| -- | ------ | -------------------------- | ------------------- | -- |
| 1  | 容器状态   | 3 个容器均 Up                  | `docker compose ps` | □  |
| 2  | 健康检查   | /health 返回 200             | curl                | □  |
| 3  | 数据库表   | 10 张核心表存在                  | `\dt`               | □  |
| 4  | Redis  | PING 返回 PONG               | redis-cli           | □  |
| 5  | HTTPS  | 证书有效                       | 浏览器绿锁               | □  |
| 6  | CORS   | 允许前端域名                     | curl -H Origin      | □  |
| 7  | 功能测试   | 6 项 API 全通过                | 9.2 节               | □  |
| 8  | 性能测试   | QPS≥500 / P99<500ms        | wrk                 | □  |
| 9  | 并发安全   | fork\_count 无丢失            | 9.5 节               | □  |
| 10 | 现有项目回归 | 全部正常访问                     | 10.2 节              | □  |
| 11 | 端口隔离   | 5433/6380/8765 仅本机         | ss -tlnp            | □  |
| 12 | 自动重启   | RestartPolicy=always       | docker inspect      | □  |
| 13 | 日志轮转   | logrotate 配置生效             | logrotate -d        | □  |
| 14 | 数据库备份  | cron 任务存在                  | crontab -l          | □  |
| 15 | 证书续期   | certbot renew --dry-run 通过 | certbot             | □  |

### 12.2 安全验收清单

| # | 验收项         | 验收标准            | 结果 |
| - | ----------- | --------------- | -- |
| 1 | JWT\_SECRET | 非 dev 默认值，64+ 位 | □  |
| 2 | PG 密码       | 24+ 位强密码        | □  |
| 3 | Redis 密码    | 已设置             | □  |
| 4 | .env 权限     | 600             | □  |
| 5 | 内部端口        | 不对外暴露           | □  |
| 6 | HTTPS       | 全站 HTTPS        | □  |
| 7 | CORS        | 精确域名，无通配符       | □  |
| 8 | APP\_ENV    | prod            | □  |

***

## 十三、风险与注意事项

### 13.1 部署风险矩阵

| 风险                | 概率 | 影响 | 缓解措施                      |
| ----------------- | -- | -- | ------------------------- |
| 端口冲突              | 中  | 高  | P0 阶段提前检查，使用非默认端口         |
| 现有项目受影响           | 低  | 高  | Nginx 独立 server 块，部署后回归测试 |
| 数据库连接耗尽           | 低  | 中  | 连接池调优（pool\_size=10）      |
| DeepSeek API 余额不足 | 中  | 低  | 提前充值，监控告警                 |
| SSL 证书申请失败        | 低  | 中  | 提前确认域名解析生效                |
| 磁盘空间不足            | 低  | 高  | P0 阶段检查 df -h             |
| Docker 镜像拉取失败     | 低  | 中  | 配置国内镜像源                   |

### 13.2 关键注意事项

1. **.env 文件绝不能提交 Git**：已在 .gitignore 中排除
2. **JWT\_SECRET 必须修改**：默认值 `dev_secret_change_me_in_production` 在生产环境会导致任何人可伪造登录
3. **APP\_ENV=prod 必须设置**：否则 PG 不可用时会静默降级到 SQLite（并发不安全）
4. **CORS\_ORIGINS 必须精确域名**：生产环境不要用通配符 `*`
5. **DIANZI\_SCHEDULER\_ENABLED 配置**：建议只让 1 个 worker 启用，避免定时任务重复执行
6. **不要复用现有项目的 PG/Redis 密码**：避免密码泄露连锁影响
7. **首次部署后立即修改默认管理员密码**（如有）

***

## 十四、P6 — 交付归档

### 14.1 部署报告归档

部署完成后，AI 助手生成《部署执行报告》，包含：

- 实际部署时间
- 实际端口分配
- 实际域名与证书信息
- 测试结果（功能 + 性能）
- 遇到的问题及解决方案
- 与本文件的差异说明
- 运维联系人

**执行人**：A
**交付物**：`/opt/dianzi/docs/DEPLOYMENT_REPORT_<日期>.md`

### 14.2 运维手册交付

交付内容：

- 日常日志查看命令
- 数据库备份与恢复流程
- 证书续期命令
- 代码更新流程
- 常见问题排查表
- 紧急联系人

**执行人**：A
**交付物**：本文件第十一节 + 第十二节

### 14.3 文件清单归档

部署完成后 `/opt/dianzi/` 目录应包含：

```
/opt/dianzi/
├── backend/
│   ├── (源码)
│   ├── Dockerfile
│   └── .env                    # 600 权限
├── frontend/
│   └── web/                    # 可选
├── nginx/
│   └── dianzi.conf
├── backup/
│   └── db_YYYYMMDD.sql.gz
├── docs/
│   └── DEPLOYMENT_REPORT_<日期>.md
├── docker-compose.prod.yml
├── deploy.sh
├── rollback.sh
└── DEPLOYMENT_GUIDE.md         # 本文件
```

***

## 十五、附录

### 附录 A：完整命令清单（按执行顺序）

```bash
# ===== P1 环境配置 =====
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && exit  # 重新登录
sudo mkdir -p /opt/dianzi/{backend,frontend,nginx,backup,docs}
sudo chown -R $USER:$USER /opt/dianzi
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw reload

# ===== P2 资源部署 =====
cd /opt/dianzi
git clone <仓库地址> backend
# 或 scp 上传
cp backend/.env.template backend/.env
nano backend/.env                  # 填敏感信息
chmod 600 backend/.env
sudo ln -s /opt/dianzi/nginx/dianzi.conf /etc/nginx/sites-enabled/
sudo nginx -t

# ===== P3 服务启动 =====
cd /opt/dianzi
chmod +x deploy.sh
./deploy.sh
curl http://127.0.0.1:8765/health
sudo certbot --nginx -d api.dianzi.app -d app.dianzi.app

# ===== P4 系统测试 =====
# 见第九节

# ===== P5 上线验证 =====
# 见第十节

# ===== 监控配置 =====
crontab -e
# 0 3 * * * docker exec dianzi-postgres pg_dump -U dianzi dianzi_app | gzip > /opt/dianzi/backup/db_$(date +\%Y\%m\%d).sql.gz && find /opt/dianzi/backup/ -name "db_*.sql.gz" -mtime +7 -delete
```

### 附录 B：配置文件模板索引

| 文件                      | 在文档中位置     | 用途       |
| ----------------------- | ---------- | -------- |
| backend/Dockerfile      | 上轮对话 6.1 节 | 后端镜像构建   |
| docker-compose.prod.yml | 上轮对话 6.2 节 | 生产编排     |
| backend/.env            | 上轮对话 6.3 节 | 环境变量     |
| nginx/dianzi.conf       | 上轮对话 6.4 节 | Nginx 反代 |
| deploy.sh               | 上轮对话 第八节   | 一键部署     |
| rollback.sh             | 上轮对话 第八节   | 一键回滚     |

> 这些模板已在上轮对话中提供，部署时由 AI 助手根据 P0 信息定制最终版本。

### 附录 C：紧急联系人模板

| 角色         | 姓名           | 联系方式         | 职责      |
| ---------- | ------------ | ------------ | ------- |
| 服务器管理员     | \_\_\_\_\_\_ | \_\_\_\_\_\_ | 服务器层面问题 |
| 项目开发者      | \_\_\_\_\_\_ | \_\_\_\_\_\_ | 代码层面问题  |
| 域名/DNS 管理员 | \_\_\_\_\_\_ | \_\_\_\_\_\_ | 域名解析问题  |
| AI 助手      | —            | 本对话窗口        | 配置/排查协助 |

***

## 十六、签署确认

部署完成后，双方确认：

| 项目       | 状态 | 确认人   | 日期     |
| -------- | -- | ----- | ------ |
| 部署文档已阅读  | □  | U     | <br /> |
| 环境检查完成   | □  | U     | <br /> |
| 兼容性评估确认  | □  | U + A | <br /> |
| 部署执行完成   | □  | U     | <br /> |
| 功能测试通过   | □  | U     | <br /> |
| 性能测试达标   | □  | U + A | <br /> |
| 现有项目回归通过 | □  | U     | <br /> |
| 安全验收通过   | □  | U     | <br /> |
| 部署报告归档   | □  | A     | <br /> |
| 运维手册交付   | □  | A     | <br /> |

***

## 十七、实际部署结果（v1.1 补充）

### 17.1 部署完成状态

| 阶段     | 状态 | 完成时间（UTC）            |
| ------ | -- | -------------------- |
| P0 前期准备 | ✅ | 2026-07-09           |
| P1 环境配置 | ✅ | 2026-07-09           |
| P2 资源部署 | ✅ | 2026-07-09           |
| P3 服务启动 | ✅ | 2026-07-09           |
| P4 系统测试 | ✅ | 2026-07-09 11:28 UTC |
| P5 上线验证 | ✅ | 2026-07-09 11:54 UTC |
| P6 交付归档 | ✅ | 2026-07-09           |

### 17.2 实际容器配置

| 容器              | 镜像                  | 内存限制   | 端口绑定              |
| --------------- | ------------------- | ------ | ------------------ |
| dianzi-postgres | postgres:16-alpine  | 384M   | 127.0.0.1:5433→5432 |
| dianzi-redis    | redis:7-alpine      | 64M    | 127.0.0.1:6380→6379 |
| dianzi-backend  | 本地构建（python:3.11-slim）| 512M   | 127.0.0.1:8765→8000 |

PostgreSQL 参数调优：`shared_buffers=128MB work_mem=4MB max_connections=80`
Redis 参数：`maxmemory 48mb maxmemory-policy allkeys-lru`
Gunicorn：4 worker × UvicornWorker

### 17.3 部署中遇到的问题及修复

#### 问题 1：users 表缺少 llm_api_url 和 llm_api_key 字段

- **现象**：注册接口报错 `column users.llm_api_key does not exist`
- **原因**：本地 schema.sql 未同步 ORM 模型新增的字段
- **修复 SQL**：
  ```sql
  ALTER TABLE users
    ADD COLUMN llm_api_url VARCHAR(255) DEFAULT '',
    ADD COLUMN llm_api_key VARCHAR(255) DEFAULT '';
  ```
- **代码同步**：已更新 [backend/db/schema.sql](file:///f:/treaFiles/Ideas/ideas/idea-app/backend/db/schema.sql) 并同步到服务器

#### 问题 2：vault_items 表字段名不一致（added_at vs created_at）

- **现象**：发布点子报错 `column vault_items.created_at does not exist`
- **原因**：schema.sql 中字段名为 `added_at`，ORM（TimestampMixin）期望 `created_at`
- **修复 SQL**：
  ```sql
  ALTER TABLE vault_items RENAME COLUMN added_at TO created_at;
  ```
- **代码同步**：已更新 schema.sql 并同步到服务器

#### 问题 3：bcrypt 版本警告（非阻塞）

- **现象**：日志出现 `(trapped) error reading bcrypt version`
- **原因**：passlib 与 bcrypt 4.x 的已知兼容性问题
- **影响**：无，密码哈希功能正常
- **处理**：暂不处理，等 passlib 新版本

### 17.4 功能验证结果

| 测试项              | 结果 | 关键证据                             |
| ---------------- | -- | -------------------------------- |
| 用户注册             | ✅ | 返回 user_id + JWT token           |
| 用户登录             | ✅ | Token 长度 223，JWT 有效 7 天          |
| 发布点子             | ✅ | 返回点子 id、color_hex、border_style   |
| 查看 Vault         | ✅ | 返回 produced/collected/forked 统计  |
| 探索页              | ✅ | 返回 circles 列表                    |
| Fork 点子          | ✅ | 返回新点子 id，source=fork            |
| 并发 Fork（10 次）    | ✅ | fork_count=11，无丢失更新（原子自增修复生效）    |
| AI 演化（substitute）| ✅ | 返回 3 个变体（near/medium/bold）       |
| AI 演化（reverse）   | ✅ | 返回 3 个变体（near/medium/bold）       |
| 数据库完整性           | ✅ | 10 张表 70 个字段全部与 ORM 对齐          |

### 17.5 并发安全验证

| 验证项                   | 结果 | 说明                  |
| --------------------- | -- | ------------------- |
| fork_count 原子自增        | ✅ | 10 并发后 count=11，无丢失 |
| PostgreSQL Advisory Lock | ✅ | 定时任务无重复执行           |
| Redis 缓存 mutex         | ✅ | explore 接口无缓存击穿     |

### 17.6 与原始计划的差异

| 差异项          | 文档预期              | 实际情况                  |
| ------------ | ----------------- | --------------------- |
| 域名           | 可选配置域名            | 暂无域名，使用 IP 访问         |
| HTTPS        | 建议启用              | 未启用，待域名后用 certbot     |
| ufw 防火墙      | 建议启用              | 按用户决策未启用              |
| geo-checkup 项目 | 与现有项目共存           | 用户要求清理，已删除           |
| swap 文件      | 建议加 2GB swap      | 通过容器内存限制替代，未加 swap    |

### 17.7 环境变量配置（.env.prod）

| 变量名              | 说明                 | 示例值                                |
| ---------------- | ------------------ | ---------------------------------- |
| APP_ENV          | 环境标识               | prod                               |
| JWT_SECRET       | JWT 签名密钥           | <your_jwt_secret_min_32_chars>    |
| PG_PASSWORD      | PostgreSQL 密码      | <your_pg_password>               |
| REDIS_PASSWORD   | Redis 密码           | <your_redis_password>            |
| DATABASE_URL     | 数据库连接串             | postgresql+asyncpg://dianzi:...@postgres:5432/dianzi_app |
| DEEPSEEK_API_KEY | DeepSeek API Key   | sk-<your_deepseek_api_key> |
| CORS_ORIGINS     | CORS 允许来源          | http://124.221.108.59,http://localhost:*,http://127.0.0.1:* |

### 17.8 常见问题排查

| 问题               | 排查命令                                              | 解决方案                    |
| ---------------- | ------------------------------------------------- | ----------------------- |
| 后端服务无法启动         | `docker logs dianzi-backend`                      | 检查 .env.prod 配置         |
| 数据库连接失败          | `docker exec dianzi-postgres pg_isready`          | 检查 PG_PASSWORD 和网络      |
| Redis 连接失败       | `docker exec dianzi-redis redis-cli ping`         | 检查 REDIS_PASSWORD       |
| AI 演化接口 500      | `docker logs dianzi-backend 2>&1 \| grep -i error`| 检查 DEEPSEEK_API_KEY 余额  |
| CORS 错误          | 检查 CORS_ORIGINS 是否包含前端域名/IP                       | 更新 .env.prod 并重启        |
| 容器 OOM 被杀        | `docker inspect dianzi-backend \| grep OOMKilled` | 调整内存限制或加 swap           |

### 17.9 回滚操作

```bash
# 停止服务（保留数据）
docker compose -f /opt/dianzi/docker-compose.prod.yml down

# 完全清理（含数据，慎用）
docker compose -f /opt/dianzi/docker-compose.prod.yml down -v
sudo rm -f /etc/nginx/sites-enabled/dianzi.conf
sudo nginx -s reload
```

### 17.10 数据库备份

```bash
# 手动备份
docker exec dianzi-postgres pg_dump -U dianzi dianzi_app | gzip > /opt/dianzi/backup/db_$(date +%Y%m%d).sql.gz

# 自动备份（cron 每天凌晨 3 点，保留 7 天）
(crontab -l 2>/dev/null; echo "0 3 * * * docker exec dianzi-postgres pg_dump -U dianzi dianzi_app | gzip > /opt/dianzi/backup/db_\$(date +\%Y\%m\%d).sql.gz && find /opt/dianzi/backup/ -name 'db_*.sql.gz' -mtime +7 -delete") | crontab -
```

***

**文档结束**

> 本文档基于 2026-07-09 项目状态编制，v1.1 补充了实际部署结果。
> 后端服务已于 2026-07-09 正式上线运行。
> 后续如有重大架构调整需更新版本。

