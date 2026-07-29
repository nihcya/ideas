#!/bin/bash
# ============================================================
# 电子点子 App 一键部署脚本
# 服务器：<your_server_ip>
# 用法：cd /opt/dianzi && ./deploy.sh
# ============================================================
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

print_step() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] $1${NC}"
}
print_warn() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] $1${NC}"
}
print_err() {
    echo -e "${RED}[$(date +%H:%M:%S)] $1${NC}"
}

# ===== 0. 前置检查 =====
print_step "步骤 0/7: 环境检查..."

command -v docker >/dev/null 2>&1 || { print_err "Docker 未安装，退出"; exit 1; }
[ -f docker-compose.prod.yml ] || { print_err "docker-compose.prod.yml 不存在"; exit 1; }
[ -f backend/.env ] || {
    print_warn "backend/.env 不存在，尝试从 .env.prod 复制..."
    [ -f backend/.env.prod ] && cp backend/.env.prod backend/.env || { print_err "backend/.env 和 .env.prod 都不存在"; exit 1; }
}
chmod 600 backend/.env
print_step "环境检查通过"

# ===== 1. 清理旧的 geo-checkup 项目（如存在）=====
print_step "步骤 1/7: 检查并清理旧项目..."
if docker ps -a --format '{{.Names}}' | grep -q '^geo-checkup$'; then
    print_warn "发现旧项目 geo-checkup 容器，停止并删除..."
    docker stop geo-checkup 2>/dev/null || true
    docker rm geo-checkup 2>/dev/null || true
    print_step "geo-checkup 已清理"
else
    print_step "无 geo-checkup 残留，跳过"
fi

# ===== 2. 构建后端镜像 =====
print_step "步骤 2/7: 构建后端镜像（首次约 3-5 分钟）..."
docker compose -f docker-compose.prod.yml build backend

# ===== 3. 启动所有服务 =====
print_step "步骤 3/7: 启动 PG/Redis/Backend..."
docker compose -f docker-compose.prod.yml up -d

# ===== 4. 等待健康检查 =====
print_step "步骤 4/7: 等待后端健康检查（最多 60 秒）..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8765/health >/dev/null 2>&1; then
        print_step "后端健康检查通过"
        break
    fi
    if [ $i -eq 30 ]; then
        print_err "健康检查超时，查看后端日志："
        docker compose -f docker-compose.prod.yml logs --tail=30 backend
        exit 1
    fi
    sleep 2
done

# ===== 5. 验证依赖服务 =====
print_step "步骤 5/7: 验证 PG/Redis..."
docker exec dianzi-postgres pg_isready -U dianzi -d dianzi_app
docker exec dianzi-redis redis-cli -a "$(grep REDIS_PASSWORD backend/.env | cut -d= -f2)" ping 2>/dev/null | grep -q PONG && echo "Redis OK" || print_warn "Redis 验证失败"

# ===== 6. 重载 Nginx =====
print_step "步骤 6/7: 配置并重载 Nginx..."
if ! command -v nginx >/dev/null 2>&1; then
    print_warn "Nginx 未安装，正在安装..."
    sudo apt update -qq && sudo apt install -y nginx >/dev/null
fi
sudo mkdir -p /etc/nginx/sites-enabled
if [ ! -L /etc/nginx/sites-enabled/dianzi.conf ]; then
    sudo ln -s /opt/dianzi/nginx/dianzi.conf /etc/nginx/sites-enabled/dianzi.conf
fi
sudo nginx -t && sudo systemctl reload nginx || { print_err "Nginx 配置错误"; exit 1; }

# ===== 7. 完成 =====
print_step "步骤 7/7: 部署完成!"
echo ""
echo "============================================"
echo "  部署信息"
echo "============================================"
echo "  服务器 IP:   <your_server_ip>"
echo "  API 健康:    http://<your_server_ip>/health"
echo "  API 接口:    http://<your_server_ip>/api/"
echo "  Swagger:     http://<your_server_ip>/docs"
echo "  Web 前端:    http://<your_server_ip>/  (需上传前端产物)"
echo "============================================"
echo ""
echo "常用命令:"
echo "  查看日志:    docker logs -f dianzi-backend"
echo "  重启后端:    docker compose -f docker-compose.prod.yml restart backend"
echo "  停止所有:    ./rollback.sh"
echo ""
