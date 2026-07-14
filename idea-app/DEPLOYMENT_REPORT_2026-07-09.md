# 电子点子 App 部署执行报告

| 项目     | 内容                          |
| ------ | --------------------------- |
| 项目名称   | 电子点子 App（Dianzi App）         |
| 报告日期   | 2026-07-09                  |
| 报告版本   | v1.0                        |
| 部署状态   | ✅ 成功上线                      |
| 服务地址   | http://124.221.108.59       |
| 部署模式   | Docker Compose 隔离部署 + Nginx |

## 一、实际部署信息

### 1.1 部署时间

| 阶段     | 完成时间（UTC）              | 状态 |
| ------ | ---------------------- | -- |
| P0 前期准备 | 2026-07-09             | ✅  |
| P1 环境配置 | 2026-07-09             | ✅  |
| P2 资源部署 | 2026-07-09             | ✅  |
| P3 服务启动 | 2026-07-09             | ✅  |
| P4 系统测试 | 2026-07-09 11:28 UTC   | ✅  |
| P5 上线验证 | 2026-07-09 11:54 UTC   | ✅  |
| P6 交付归档 | 2026-07-09             | 🔄 |

### 1.2 实际端口分配

| 服务        | 容器内端口 | 宿主机绑定              | 对外暴露 |
| --------- | ----- | ------------------ | ---- |
| Nginx     | 80    | 0.0.0.0:80         | ✅    |
| Backend   | 8000  | 127.0.0.1:8765     | ❌    |
| PostgreSQL | 5432  | 127.0.0.1:5433     | ❌    |
| Redis     | 6379  | 127.0.0.1:6380     | ❌    |

### 1.3 域名与证书

| 项目     | 实际情况                 |
| ------ | -------------------- |
| 域名     | 暂无，使用 IP 访问          |
| 访问方式   | http://124.221.108.59 |
| HTTPS  | 未启用（待域名申请后用 certbot） |

### 1.4 容器资源限制

| 容器              | 内存限制   | 实际占用（估）  |
| --------------- | ------ | -------- |
| dianzi-postgres | 384M   | ~150M    |
| dianzi-redis    | 64M    | ~10M     |
| dianzi-backend  | 512M   | ~200M    |
| **合计**          | 960M   | ~360M    |

服务器总内存 3.3GB，部署后仍有充足余量。

## 二、测试结果

### 2.1 功能测试结果

| 测试项              | 结果 | 关键证据                                                                  |
| ---------------- | -- | --------------------------------------------------------------------- |
| 用户注册             | ✅ | 返回 user_id + JWT token                                                |
| 用户登录             | ✅ | Token 长度 223，JWT 有效 7 天                                               |
| 发布点子             | ✅ | 返回点子 id、color_hex、border_style                                        |
| 查看 Vault         | ✅ | 返回 produced/collected/forked_by_others 统计 + circles 列表                |
| 探索页              | ✅ | 返回 circles 列表，is_own 字段正确                                             |
| Fork 点子          | ✅ | 返回新点子 id，source=fork                                                  |
| **并发 Fork（10 次）** | ✅ | fork_count=11，**无丢失更新**，原子自增修复生效                                      |
| **AI 演化（substitute）** | ✅ | 返回 3 个变体（near/medium/bold），DeepSeek 调用成功                             |
| **AI 演化（reverse）**   | ✅ | 返回 3 个变体（near/medium/bold），演化质量良好                                    |
| 数据库写入            | ✅ | 12 条点子记录，status 全部为 active                                           |

### 2.2 并发安全验证结果

| 验证项                 | 结果 | 说明                          |
| ------------------- | -- | --------------------------- |
| fork_count 原子自增      | ✅ | 10 并发后 count=11，无丢失更新        |
| PostgreSQL Advisory Lock | ✅ | 定时任务无重复执行                   |
| Redis 缓存 mutex       | ✅ | explore 接口无缓存击穿             |

### 2.3 数据库完整性验证

所有 10 张表（users、ideas、vault_items、fork_relations、spark_questions、spark_drafts、spark_submissions、notifications、audit_logs、banned_words）共 70 个字段，全部与 ORM 模型对齐。

## 三、部署过程中遇到的问题及解决方案

### 问题 1：users 表缺少 llm_api_url 和 llm_api_key 字段

- **现象**：注册接口报错 `column users.llm_api_key does not exist`
- **原因**：本地 schema.sql 未同步 ORM 模型新增的字段
- **解决**：在服务器执行 `ALTER TABLE users ADD COLUMN llm_api_url VARCHAR(255) DEFAULT ''; ADD COLUMN llm_api_key VARCHAR(255) DEFAULT '';`，并同步本地 schema.sql

### 问题 2：vault_items 表字段名不一致（added_at vs created_at）

- **现象**：发布点子报错 `column vault_items.created_at does not exist`
- **原因**：schema.sql 中字段名为 `added_at`，但 ORM 通过 TimestampMixin 期望 `created_at`
- **解决**：在服务器执行 `ALTER TABLE vault_items RENAME COLUMN added_at TO created_at;`，并修复本地 schema.sql

### 问题 3：服务器未安装 jq

- **现象**：`Command 'jq' not found`
- **解决**：`sudo apt install -y jq`

### 问题 4：bash 反引号导致 URL 被当作命令执行

- **现象**：curl 请求未真正发出，TOKEN 变量为空
- **原因**：URL 用反引号包裹（`` `http://...` ``），bash 将其当作命令替换
- **解决**：URL 直接写字符串，不加反引号

### 问题 5：AI 演化接口路径和请求字段错误

- **现象**：`POST /api/ideas/spark` 返回 405 Method Not Allowed
- **原因**：正确路径是 `/api/ideas/evolve`；请求体字段是 `angle`（不是 `adapt`）
- **解决**：使用正确路径和字段名重试

### 问题 6：bcrypt 版本警告（非阻塞）

- **现象**：日志出现 `(trapped) error reading bcrypt version`
- **原因**：passlib 与 bcrypt 4.x 的已知兼容性问题
- **影响**：无，密码哈希功能正常
- **解决**：暂不处理，等 passlib 新版本

## 四、与本文件的差异说明

与 DEPLOYMENT_GUIDE.md 的差异：

| 差异项          | 文档预期                  | 实际情况                    |
| ------------ | --------------------- | ----------------------- |
| 域名           | 可选配置域名                | 暂无域名，使用 IP 访问           |
| HTTPS        | 建议启用                  | 未启用，待域名后用 certbot       |
| ufw 防火墙      | 建议启用                  | 按用户决策未启用                |
| geo-checkup 项目 | 与现有项目共存               | 用户要求清理，已删除             |
| swap 文件      | 建议加 2GB swap          | 通过容器内存限制替代，未加 swap      |

## 五、运维联系人

| 角色     | 联系方式             |
| ------ | ---------------- |
| 服务器所有者 | ubuntu@124.221.108.59 |
| AI 助手  | Trae IDE         |

## 六、后续建议

### 6.1 立即执行

1. **配置数据库自动备份**（避免数据丢失）：
   ```bash
   sudo mkdir -p /opt/dianzi/backup
   (crontab -l 2>/dev/null; echo "0 3 * * * docker exec dianzi-postgres pg_dump -U dianzi dianzi_app | gzip > /opt/dianzi/backup/db_\$(date +\%Y\%m\%d).sql.gz && find /opt/dianzi/backup/ -name 'db_*.sql.gz' -mtime +7 -delete") | crontab -
   ```

2. **同步本地 schema.sql 到服务器**（避免下次部署踩坑）：
   ```powershell
   scp f:\treaFiles\Ideas\ideas\idea-app\backend\db\schema.sql ubuntu@124.221.108.59:/opt/dianzi/backend/db/schema.sql
   ```

### 6.2 短期计划

1. **前端部署**：打包 Flutter Web 上传到 `/opt/dianzi/frontend/web`
2. **监控配置**：可选接入 Prometheus + Grafana

### 6.3 长期计划

1. **域名 + HTTPS**：购买域名后执行 `sudo certbot --nginx -d <域名>`
2. **性能优化**：根据实际流量调整 Gunicorn worker 数量
3. **bcrypt 警告消除**：等 passlib 新版本或降级 bcrypt 到 4.0.1

## 七、归档文件清单

部署完成后 `/opt/dianzi/` 目录结构：

```
/opt/dianzi/
├── backend/
│   ├── (源码)
│   ├── Dockerfile
│   ├── .env.prod              # 600 权限
│   └── db/schema.sql          # 已修复
├── frontend/                   # 待部署
├── nginx/
│   └── dianzi.conf
├── backup/                     # 待配置 cron
├── docs/
│   └── DEPLOYMENT_REPORT_2026-07-09.md
├── docker-compose.prod.yml
├── deploy.sh
├── rollback.sh
└── DEPLOYMENT_GUIDE.md
```

---

**报告人**：AI 助手
**签署日期**：2026-07-09
