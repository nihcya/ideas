# 点子 App — Beta 测试部署指南（IP 访问版）

> **适用场景**：域名尚未到位，使用 IP `124.221.108.59` 进行小范围 Beta 测试。
> **前置条件**：服务器已部署过旧版本，Nginx + Docker 均已运行。
> **操作环境**：本地 Windows + 服务器 Linux（Ubuntu）。
> **预计操作**：5 个步骤，按顺序执行即可。

---

## 第一步：轮换 DeepSeek API Key

> 旧 Key 已从代码仓库删除，但之前可能泄露过，需要换一把新的。

【在哪执行】浏览器

```
第 1 步：打开 https://platform.deepseek.com/ 并登录
第 2 步：点击左侧菜单「API Keys」
第 3 步：找到旧 Key（sk-6baecf 开头的），点 Delete 删除
第 4 步：点「Create API Key」，名称填 dianzi-beta
第 5 步：复制新 Key（sk- 开头），粘贴到记事本备用
```

---

## 第二步：上传修改后的代码到服务器

> 本地已修改 13 个文件，需要同步到服务器。

【在哪执行】本地（PowerShell 终端）

```powershell
# 第 1 步：进入项目目录
cd f:\treaFiles\Ideas\ideas\idea-app

# 第 2 步：上传后端修改的文件到服务器
scp backend\services\fade_service.py root@124.221.108.59:/opt/dianzi/backend/services/fade_service.py
scp backend\services\rate_limit.py root@124.221.108.59:/opt/dianzi/backend/services/rate_limit.py
scp backend\requirements.txt root@124.221.108.59:/opt/dianzi/backend/requirements.txt
scp backend\main.py root@124.221.108.59:/opt/dianzi/backend/main.py
scp backend\routers\auth.py root@124.221.108.59:/opt/dianzi/backend/routers/auth.py
scp backend\routers\evolve.py root@124.221.108.59:/opt/dianzi/backend/routers/evolve.py
scp backend\routers\ideas.py root@124.221.108.59:/opt/dianzi/backend/routers/ideas.py

# 第 3 步：确认上传成功（逐个回车，每次应输出文件名或无报错）
```

---

## 第三步：在服务器上更新配置并重建后端

【在哪执行】服务器（SSH 登录后的终端）

```bash
# 第 1 步：登录服务器
ssh root@124.221.108.59

# 第 2 步：进入项目目录
cd /opt/dianzi/backend

# 第 3 步：更新 .env 中的 DEEPSEEK_API_KEY
# 把 sk-xxxx 替换为你在第一步复制的新 Key
nano .env
# 在编辑器中：
#   找到 DEEPSEEK_API_KEY= 开头的那一行
#   把等号后面的旧 Key 删掉，粘贴新 Key
#   按 Ctrl+O 保存，按 Enter 确认，按 Ctrl+X 退出

# 第 4 步：确认 .env 中 CORS 允许 IP 访问
# 继续在 nano 中检查 CORS_ORIGINS 这一行
# 应该是：CORS_ORIGINS=http://124.221.108.59
# 如果不是，改成上面这个值
# 按 Ctrl+O 保存，按 Enter 确认，按 Ctrl+X 退出

# 第 5 步：重新生成 JWT 密钥（增强安全性）
openssl rand -hex 32
# 复制输出的 64 位字符串备用

# 第 6 步：把新密钥写入 .env
nano .env
# 找到 JWT_SECRET= 开头的那一行
# 把等号后面的旧值删掉，粘贴上一步生成的新值
# 按 Ctrl+O 保存，按 Enter 确认，按 Ctrl+X 退出

# 第 7 步：进入项目根目录，重建后端镜像
cd /opt/dianzi
docker compose -f docker-compose.prod.yml build backend
# 预期输出末尾：Successfully tagged ... 或 naming to ...

# 第 8 步：用新镜像启动后端
docker compose -f docker-compose.prod.yml up -d backend
# 预期输出：Container dianzi-backend  Started

# 第 9 步：等待 5 秒后验证后端健康
sleep 5
curl http://127.0.0.1:8765/health
# 预期输出：{"status":"ok","env":"prod",...}
```

---

## 第四步：编译并部署前端

【在哪执行】本地（PowerShell 终端）

```powershell
# 第 1 步：进入前端目录
cd f:\treaFiles\Ideas\ideas\idea-app\frontend

# 第 2 步：清理旧构建产物
flutter clean

# 第 3 步：安装依赖
flutter pub get

# 第 4 步：编译 Web 版本，API 地址指向服务器 IP
flutter build web --release --dart-define=API_BASE_URL=http://124.221.108.59/api
# 预期输出末尾：Built build\web

# 第 5 步：进入构建产物目录
cd build\web

# 第 6 步：打包为 tar.gz
tar -czf ..\..\..\dianzi-web-beta.tar.gz .

# 第 7 步：上传到服务器
scp ..\..\..\dianzi-web-beta.tar.gz root@124.221.108.59:/opt/dianzi/releases/
```

【在哪执行】服务器（SSH 登录后的终端）

```bash
# 第 8 步：登录服务器
ssh root@124.221.108.59

# 第 9 步：进入项目目录
cd /opt/dianzi

# 第 10 步：创建新版本目录并解压
mkdir -p releases/beta
tar -xzf releases/dianzi-web-beta.tar.gz -C releases/beta

# 第 11 步：切换软链接指向新版本
ln -sfn releases/beta web

# 第 12 步：重载 Nginx
sudo systemctl reload nginx
# 无输出即成功

# 第 13 步：验证前端页面能打开
curl -I http://124.221.108.59
# 预期输出：HTTP/1.1 200 OK
```

---

## 第五步：逐项验证

### 5.1 验证后端 API

【在哪执行】本地（PowerShell 终端）

```powershell
# 第 1 步：验证健康检查
curl http://124.221.108.59/health
# 预期输出：{"status":"ok","env":"prod",...}

# 第 2 步：验证注册接口
curl -s -X POST http://124.221.108.59/api/auth/register `
  -H "Content-Type: application/json" `
  -d '{\"username\":\"betauser\",\"password\":\"test12345\"}'
# 预期输出：返回含 token 和 username 的 JSON

# 第 3 步：验证登录限流（连续 12 次请求）
# 在 PowerShell 中执行：
for ($i=1; $i -le 12; $i++) {
  $code = curl -s -o $null -w "%{http_code}" `
    -X POST http://124.221.108.59/api/auth/login `
    -H "Content-Type: application/json" `
    -d '{\"username\":\"betauser\",\"password\":\"wrong\"}'
  Write-Host "第 $i 次: $code"
}
# 预期输出：
#   第 1-10 次: 401
#   第 11-12 次: 429  ← 被限流拦截
```

### 5.2 验证异常脱敏

【在哪执行】服务器

```bash
# 第 4 步：故意发送非法 token 触发错误
curl -s -X POST http://127.0.0.1:8765/api/ideas \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid_token_xxx" \
  -d '{"content":"test"}'
# 预期输出：{"error":{"code":"UNAUTHORIZED","message":"token 无效或已过期"}}
# 不应出现数据库连接串或 Python 堆栈信息
```

### 5.3 验证前端功能

【在哪执行】浏览器

```
第 5 步：打开浏览器，访问 http://124.221.108.59
         预期：看到圆圈探索页面正常加载

第 6 步：点击右上角注册，创建账号，登录
         预期：登录成功后进入探索海洋

第 7 步：点击任意圆圈，查看点子详情
         预期：详情页和谱系图正常显示

第 8 步：点击「碰撞」或「演化」，测试 AI 功能
         预期：3-5 秒内返回 AI 生成的结果

第 9 步：进入「今日一点」页面
         预期：显示倒计时，输入文字后可提交
         预期：提交后跳转到点子详情页，返回后仍能看到提交内容

第 10 步：进入「设置」页面
         预期：没有"通知开关"和"清除缓存"（已移除假实现）
         预期：大模型配置和退出登录功能正常
```

### 5.4 验证淡出逻辑

【在哪执行】服务器

```bash
# 第 11 步：检查后端日志，确认 scheduler 正在运行
docker logs dianzi-backend --tail 20 2>&1 | grep -i fade
# 预期输出：包含 fade 相关的调度日志或无错误

# 第 12 步：手动触发一次淡出检查（可选，仅确认不报错）
docker exec dianzi-backend python -c "
import asyncio
from database import init_engine, get_session_factory
from services.fade_service import check_and_fade
async def test():
    await init_engine()
    async with get_session_factory()() as db:
        result = await check_and_fade(db)
        print('淡出检查结果:', result)
asyncio.run(test())
"
# 预期输出：淡出检查结果: {'faded_to_fading': 0, 'removed_from_vault': 0, 'marked_as_faded': 0, 'physically_deleted': 0}
# 数值为 0 是正常的（当前没有超过 7 天的数据）
```

---

## 第六步：设置数据库自动备份（强烈建议）

【在哪执行】服务器

```bash
# 第 1 步：登录服务器
ssh root@124.221.108.59

# 第 2 步：创建备份目录
mkdir -p /opt/dianzi/backup

# 第 3 步：创建备份脚本
cat > /opt/dianzi/backup/db_backup.sh << 'SCRIPT_EOF'
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR="/opt/dianzi/backup"
docker exec dianzi-postgres pg_dump -U dianzi dianzi_app | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +7 -delete
echo "[$DATE] backup done"
SCRIPT_EOF

# 第 4 步：赋予执行权限
chmod +x /opt/dianzi/backup/db_backup.sh

# 第 5 步：手动执行一次，验证备份正常
/opt/dianzi/backup/db_backup.sh
# 预期输出：[20260710] backup done

# 第 6 步：检查备份文件
ls -lh /opt/dianzi/backup/
# 预期输出：db_20260710.sql.gz 大小约几十 KB

# 第 7 步：设置每天凌晨 3 点自动备份
crontab -e
# 在文件末尾添加以下一行：
#   0 3 * * * /opt/dianzi/backup/db_backup.sh >> /opt/dianzi/backup/backup.log 2>&1
# nano 编辑器：Ctrl+O 保存，Enter 确认，Ctrl+X 退出
```

---

## Beta 测试注意事项

| 项目 | 说明 |
|------|------|
| **无 HTTPS** | 当前用 HTTP 传输，密码和 token 未加密。Beta 小范围可接受，正式上线前必须配 HTTPS |
| **限流已生效** | 登录 10 次/分钟、注册 5 次/分钟、AI 接口 10 次/分钟、创建点子 20 次/分钟 |
| **异常已脱敏** | 500 错误不再泄露内部细节，返回通用提示 |
| **淡出逻辑已修复** | 过期点子会被正确标记为 faded 并物理删除 |
| **前端假实现已移除** | 设置页不再有无效的"通知开关"和"清除缓存" |
| **密钥已轮换** | DeepSeek API Key 和 JWT_SECRET 都是新生成的 |
| **数据库每日备份** | 凌晨 3 点自动备份，保留最近 7 天 |

---

## 域名到位后的迁移步骤

等域名购买完成并 DNS 生效后，只需执行以下操作即可升级到正式版：

```
1. 在服务器执行：sudo certbot --nginx -d 你的域名   （申请 SSL 证书）
2. 修改 .env 中 CORS_ORIGINS=https://你的域名
3. 本地重新编译前端：flutter build web --release --dart-define=API_BASE_URL=https://你的域名/api
4. 上传并部署前端到服务器
5. 重启后端：docker compose -f docker-compose.prod.yml restart backend
```

详见 [MANUAL_OPS.md](file:///f:/treaFiles/Ideas/ideas/idea-app/MANUAL_OPS.md) 中第二、三节的完整步骤。
