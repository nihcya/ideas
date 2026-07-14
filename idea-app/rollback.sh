#!/bin/bash
# ============================================================
# 电子点子 App 回滚/停止脚本
# 用法：./rollback.sh [mode]
#   无参数：停止所有服务（数据保留在 volume）
#   clean：停止并删除数据（慎用！不可恢复）
# ============================================================
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

MODE="${1:-stop}"

print_step() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] $1${NC}"
}
print_warn() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] $1${NC}"
}
print_err() {
    echo -e "${RED}[$(date +%H:%M:%S)] $1${NC}"
}

cd /opt/dianzi

if [ "$MODE" = "stop" ]; then
    print_step "停止所有服务（数据保留）..."
    docker compose -f docker-compose.prod.yml down
    print_step "已停止"
    print_warn "Nginx 配置仍保留，如需移除：sudo rm /etc/nginx/sites-enabled/dianzi.conf && sudo systemctl reload nginx"
    echo ""
    echo "重新启动: ./deploy.sh"

elif [ "$MODE" = "clean" ]; then
    print_err "⚠️  即将停止服务并删除所有数据（不可恢复）!"
    read -p "确认删除？输入 YES 继续: " confirm
    if [ "$confirm" != "YES" ]; then
        echo "已取消"
        exit 0
    fi
    print_step "停止服务并删除 volume..."
    docker compose -f docker-compose.prod.yml down -v
    sudo rm -f /etc/nginx/sites-enabled/dianzi.conf
    sudo nginx -t 2>/dev/null && sudo systemctl reload nginx 2>/dev/null || true
    print_step "已彻底清理（数据已删除）"

else
    echo "用法: ./rollback.sh [stop|clean]"
    echo "  stop  (默认): 停止服务，保留数据"
    echo "  clean       : 停止并删除所有数据（危险）"
    exit 1
fi
