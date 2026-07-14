# 点子 App — 上线前手动操作指南

> **阅读说明**：本文档每一步都标注了【在哪执行】和【执行命令】。
> - `your-domain.com` 是占位符，请替换为你的真实域名
> - `124.221.108.59` 是服务器 IP
> - 【本地】= 你的电脑终端；【服务器】= SSH 登录服务器后的终端

---

## 一、轮换已泄露的密钥

### 1.1 轮换 DeepSeek API Key

【在哪执行】浏览器

```
第 1 步：打开 https://platform.deepseek.com/ 并登录
第 2 步：点击左侧菜单「API Keys」
第 3 步：找到旧 Key（sk-6baecf 开头的），点击 Delete 删除
第 4 步：点击「Create API Key」，输入名称如 "dianzi-prod"
第 5 步：复制新生成的 Key（sk- 开头），粘贴到记事本备用
```

### 1.2 重新生成 JWT 密钥

【在哪执行】服务器

```bash
# 第 1 步：登录服务器
ssh root@124.221.108.59

# 第 2 步：生成新的随机密钥（复制输出结果备用）
openssl rand -hex 32
# 输出示例：a3f5e8b2c1d4f7a6...（64 个字符）

# 第 3 步：用新密钥替换 .env 中的旧 JWT_SECRET
# 把下面命令中的 <第2步的输出> 替换为你刚才复制的那串字符
nano /opt/dianzi/backend/.env
# 在编辑器中：
#   找到 JWT_SECRET= 开头的那一行
#   把等号后面的旧值删掉，粘贴你第 2 步生成的新值
#   按 Ctrl+O 保存，按 Enter 确认，按 Ctrl+X 退出
```

### 1.3 更新 DeepSeek API Key 到服务器

【在哪执行】服务器（接上一步，已登录）

```bash
# 第 1 步：编辑配置文件
nano /opt/dianzi/backend/.env
# 在编辑器中：
#   找到 DEEPSEEK_API_KEY= 开头的那一行
#   把等号后面的旧 Key 删掉，粘贴你在 1.1 第 5 步保存的新 Key
#   按 Ctrl+O 保存，按 Enter 确认，按 Ctrl+X 退出
```

### 1.4 重启后端使新配置生效

【在哪执行】服务器（接上一步）

```bash
# 第 1 步：进入项目目录
cd /opt/dianzi

# 第 2 步：重启后端容器
docker compose -f docker-compose.prod.yml restart backend

# 第 3 步：等待 5 秒后检查健康状态
sleep 5
curl http://127.0.0.1:8765/health
# 预期输出：{"status":"ok","env":"prod",...}
```

---

## 二、部署 HTTPS

### 2.1 购买域名并配置 DNS

```
第 1 步：在阿里云/腾讯云/Namecheap 购买一个域名
第 2 步：进入域名管理后台，添加 DNS 解析记录：
         - 记录类型：A
         - 主机记录：@
         - 记录值：124.221.108.59
         - TTL：默认
第 3 步：等待 5-30 分钟 DNS 生效
```

【在哪执行】本地（验证 DNS 是否生效）

```bash
# 把 your-domain.com 替换为你的真实域名
nslookup your-domain.com
# 预期输出中应包含：Address: 124.221.108.59
```

### 2.2 安装 certbot 并申请 SSL 证书

【在哪执行】服务器

```bash
# 第 1 步：登录服务器
ssh root@124.221.108.59

# 第 2 步：更新软件包列表
sudo apt update

# 第 3 步：安装 certbot（申请免费 SSL 证书的工具）
sudo apt install certbot python3-certbot-nginx -y

# 第 4 步：申请 SSL 证书
# 把 your-domain.com 替换为你的真实域名
sudo certbot --nginx -d your-domain.com
# 交互提示依次回答：
#   - 输入你的邮箱（用于接收证书过期通知）
#   - 输入 A 同意服务条款
#   - 输入 N 不分享邮箱给 EFF
#   - 输入 2 选择「Redirect」自动把 HTTP 跳转到 HTTPS
# 预期输出末尾：Congratulations! You have successfully enabled HTTPS
```

### 2.3 部署 HTTPS Nginx 配置

【在哪执行】服务器（接上一步）

```bash
# 第 1 步：备份现有 Nginx 配置
sudo cp /etc/nginx/sites-available/dianzi /etc/nginx/sites-available/dianzi.bak

# 第 2 步：将项目中的 nginx-https.conf 中的域名替换为真实域名
# 先查看模板内容
cat /opt/dianzi/nginx/nginx-https.conf
# 如果服务器上没有这个文件，从本地项目上传：
#   （在本地终端执行）
#   scp nginx/nginx-https.conf root@124.221.108.59:/opt/dianzi/nginx/

# 第 3 步：替换模板中的 your-domain.com 为真实域名
# 把 your-domain.com 替换为你的真实域名
sudo sed -i 's/your-domain.com/你的真实域名/g' /opt/dianzi/nginx/nginx-https.conf

# 第 4 步：复制配置到 Nginx 目录
sudo cp /opt/dianzi/nginx/nginx-https.conf /etc/nginx/sites-available/dianzi

# 第 5 步：测试 Nginx 配置语法是否正确
sudo nginx -t
# 预期输出：syntax is ok / test is successful

# 第 6 步：重载 Nginx 使配置生效
sudo systemctl reload nginx
```

### 2.4 更新后端 CORS 为 HTTPS 域名

【在哪执行】服务器（接上一步）

```bash
# 第 1 步：编辑配置文件
nano /opt/dianzi/backend/.env
# 在编辑器中：
#   找到 CORS_ORIGINS= 开头的那一行
#   把整行改为（替换为你的真实域名）：
#   CORS_ORIGINS=https://你的真实域名
#   按 Ctrl+O 保存，按 Enter 确认，按 Ctrl+X 退出

# 第 2 步：重启后端
cd /opt/dianzi
docker compose -f docker-compose.prod.yml restart backend
```

### 2.5 验证证书自动续期

【在哪执行】服务器（接上一步）

```bash
# Let's Encrypt 证书有效期 90 天，需验证自动续期是否正常
sudo certbot renew --dry-run
# 预期输出末尾：Congratulations, all simulated renewals succeeded
```

### 2.6 验证 HTTPS 部署

【在哪执行】本地

```bash
# 第 1 步：验证 HTTPS 能正常访问（替换为真实域名）
curl -I https://your-domain.com
# 预期输出：HTTP/2 200

# 第 2 步：验证 HTTP 会自动跳转到 HTTPS
curl -I http://your-domain.com
# 预期输出：HTTP/1.1 301 Moved Permanently，Location 含 https://

# 第 3 步：验证安全响应头是否存在
curl -I https://your-domain.com 2>&1 | grep -i strict-transport-security
# 预期输出：strict-transport-security: max-age=31536000; includeSubDomains

# 第 4 步：验证 API 接口能正常调用
curl https://your-domain.com/health
# 预期输出：{"status":"ok","env":"prod",...}
```

---

## 三、重新编译并部署前端

### 3.1 本地编译前端（指定 HTTPS 域名）

【在哪执行】本地

```bash
# 第 1 步：进入前端目录
cd f:\treaFiles\Ideas\ideas\idea-app\frontend

# 第 2 步：清理旧构建
flutter clean

# 第 3 步：安装依赖
flutter pub get

# 第 4 步：编译 Web 版本（把 your-domain.com 替换为真实域名）
flutter build web --release --dart-define=API_BASE_URL=https://your-domain.com/api
# 预期输出末尾：Built build\web  或  Compiling lib\main.dart for the Web...
```

### 3.2 打包并上传到服务器

【在哪执行】本地

```bash
# 第 1 步：进入构建产物目录
cd f:\treaFiles\Ideas\ideas\idea-app\frontend\build\web

# 第 2 步：打包为 tar.gz
tar -czf f:\treaFiles\Ideas\ideas\idea-app\dianzi-web-build-v2.0.tar.gz .

# 第 3 步：上传到服务器
scp f:\treaFiles\Ideas\ideas\idea-app\dianzi-web-build-v2.0.tar.gz root@124.221.108.59:/opt/dianzi/releases/
```

### 3.3 在服务器上部署前端

【在哪执行】服务器

```bash
# 第 1 步：登录服务器
ssh root@124.221.108.59

# 第 2 步：进入项目目录
cd /opt/dianzi

# 第 3 步：创建新版本目录并解压
mkdir -p releases/v2.0
tar -xzf releases/dianzi-web-build-v2.0.tar.gz -C releases/v2.0

# 第 4 步：切换软链接指向新版本
ln -sfn releases/v2.0 web

# 第 5 步：重载 Nginx
sudo systemctl reload nginx

# 第 6 步：验证前端页面能打开
curl -I https://your-domain.com
# 预期输出：HTTP/2 200
```

---

## 四、在服务器安装 slowapi 依赖

> 代码中已添加 slowapi 限流库，服务器需要安装该依赖才能生效。

【在哪执行】服务器

```bash
# 第 1 步：登录服务器
ssh root@124.221.108.59

# 第 2 步：进入项目目录
cd /opt/dianzi

# 第 3 步：重新构建后端镜像（会根据新的 requirements.txt 安装 slowapi）
docker compose -f docker-compose.prod.yml build backend

# 第 4 步：用新镜像重启后端
docker compose -f docker-compose.prod.yml up -d backend

# 第 5 步：等待 5 秒后验证健康状态
sleep 5
curl http://127.0.0.1:8765/health
# 预期输出：{"status":"ok","env":"prod",...}
```

### 验证限流是否生效

【在哪执行】服务器（接上一步）

```bash
# 第 1 步：连续发送 11 次登录请求
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "第 $i 次: %{http_code}\n" \
    -X POST http://127.0.0.1:8765/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"test","password":"wrong"}'
done

# 预期输出：
#   第 1 次: 401
#   第 2 次: 401
#   ...
#   第 10 次: 401
#   第 11 次: 429    ← 第 11 次被限流拦截
```

---

## 五、设置数据库自动备份

### 5.1 创建备份脚本

【在哪执行】服务器

```bash
# 第 1 步：登录服务器
ssh root@124.221.108.59

# 第 2 步：创建备份目录
mkdir -p /opt/dianzi/backup

# 第 3 步：创建备份脚本文件
cat > /opt/dianzi/backup/db_backup.sh << 'SCRIPT_EOF'
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR="/opt/dianzi/backup"
docker exec dianzi-postgres pg_dump -U dianzi dianzi_app | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +7 -delete
echo "[$DATE] backup done"
SCRIPT_EOF

# 第 4 步：赋予脚本执行权限
chmod +x /opt/dianzi/backup/db_backup.sh
```

### 5.2 设置每天自动执行

【在哪执行】服务器（接上一步）

```bash
# 第 1 步：编辑定时任务
crontab -e

# 第 2 步：在文件末尾添加以下一行（然后保存退出）
0 3 * * * /opt/dianzi/backup/db_backup.sh >> /opt/dianzi/backup/backup.log 2>&1
# 如果用的是 nano 编辑器：按 Ctrl+O 保存，Enter 确认，Ctrl+X 退出
# 如果用的是 vi 编辑器：按 i 进入插入模式，粘贴内容，按 Esc，输入 :wq 保存退出
```

### 5.3 验证备份功能

【在哪执行】服务器（接上一步）

```bash
# 第 1 步：手动执行一次备份
/opt/dianzi/backup/db_backup.sh
# 预期输出：[20260710] backup done

# 第 2 步：检查备份文件是否生成
ls -lh /opt/dianzi/backup/
# 预期输出：db_20260710.sql.gz 大小约几十 KB

# 第 3 步：验证备份文件内容是否完整（解压查看前几行）
gunzip -c /opt/dianzi/backup/db_$(date +%Y%m%d).sql.gz | head -20
# 预期输出：PostgreSQL database dump 开头的 SQL 语句
```

---

## 六、最终验证清单

> 完成以上所有操作后，在【本地】终端逐项执行以下命令验证。

### 6.1 HTTPS 和安全头验证

```bash
# 第 1 步：验证 HTTPS 正常（替换 your-domain.com 为真实域名）
curl -I https://your-domain.com
# 预期：HTTP/2 200

# 第 2 步：验证 HTTP 自动跳转
curl -I http://your-domain.com
# 预期：301 Moved Permanently

# 第 3 步：验证 HSTS 安全头
curl -sI https://your-domain.com | grep -i strict-transport-security
# 预期：strict-transport-security: max-age=31536000; includeSubDomains
```

### 6.2 API 功能验证

```bash
# 第 4 步：验证健康检查
curl https://your-domain.com/health
# 预期：{"status":"ok","env":"prod",...}

# 第 5 步：验证注册接口
curl -s -X POST https://your-domain.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"verifyuser","password":"test12345"}'
# 预期：返回含 token 的 JSON

# 第 6 步：验证限流（连续 12 次请求，看是否出现 429）
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "第 $i 次: %{http_code}\n" \
    -X POST https://your-domain.com/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"verifyuser","password":"wrong"}'
done
# 预期：前 10 次返回 401，第 11 次起返回 429
```

### 6.3 前端页面验证

```
第 7 步：打开浏览器，访问 https://your-domain.com
         预期：看到圆圈探索页面正常加载

第 8 步：点击页面右上角注册，创建账号，登录
         预期：登录成功后进入探索海洋

第 9 步：点击任意圆圈，查看点子详情
         预期：详情页和谱系图正常显示

第 10 步：进入「设置」页面
         预期：没有"通知开关"和"清除缓存"两个假功能
         预期：大模型配置和退出登录功能正常
```

### 6.4 异常脱敏验证

【在哪执行】服务器

```bash
# 第 11 步：故意触发一个 500 错误，验证返回信息不泄露内部细节
# 构造一个会导致异常的请求（如发送非法 JSON）
curl -s -X POST http://127.0.0.1:8765/api/ideas \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid_token" \
  -d '{"content":"test"}'
# 预期：返回 {"error":{"code":"UNAUTHORIZED","message":"token 无效或已过期"}}
# 而非返回数据库连接串或 Python 堆栈信息
```

---

## 附录：文件变更清单

以下 13 个文件已在代码层面完成修改，部署时需同步到服务器：

| 文件 | 变更 | 说明 |
|------|------|------|
| `.gitignore` | 编辑 | 增加 `.env.prod` 排除规则 |
| `backend/.env.prod` | 删除 | 已从项目目录移除 |
| `backend/.env.prod.example` | 新建 | 脱敏配置模板 |
| `backend/services/fade_service.py` | 编辑 | 修复淡出逻辑 Bug |
| `backend/services/rate_limit.py` | 新建 | 限流配置模块 |
| `backend/requirements.txt` | 编辑 | 添加 slowapi |
| `backend/main.py` | 编辑 | 注册限流器 + 异常脱敏 |
| `backend/routers/auth.py` | 编辑 | 登录/注册加速流 |
| `backend/routers/evolve.py` | 编辑 | 碰撞/演化加速流 |
| `backend/routers/ideas.py` | 编辑 | 创建点子加速流 |
| `nginx/nginx-https.conf` | 新建 | HTTPS Nginx 配置 |
| `frontend/lib/screens/settings_screen.dart` | 编辑 | 移除假实现 |
| `frontend/lib/screens/spark_screen.dart` | 编辑 | 修复倒计时 + 内容显示 |
