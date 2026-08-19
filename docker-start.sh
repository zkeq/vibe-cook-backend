#!/bin/bash

# Vibe Cook Backend - Docker 一键启动脚本
# 使用方法: ./docker-start.sh [start|stop|restart|logs|status]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker未安装，请先安装Docker"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
}

# 检查配置文件
check_config() {
    if [ ! -f "config.yaml" ]; then
        print_warn "config.yaml不存在，使用Docker配置文件"
        if [ ! -f "config.docker.yaml" ]; then
            print_error "config.docker.yaml也不存在，请先创建配置文件"
            exit 1
        fi
        cp config.docker.yaml config.yaml
        print_info "已复制config.docker.yaml为config.yaml"
    fi
}

# 启动服务
start_services() {
    print_info "正在启动Vibe Cook Backend服务..."

    # 使用docker compose或docker-compose
    if docker compose version &> /dev/null; then
        docker compose up -d
    else
        docker-compose up -d
    fi

    print_info "服务启动中，等待健康检查..."
    sleep 5

    # 检查服务状态
    check_status

    print_info "✅ 服务启动成功！"
    print_info ""
    print_info "📝 访问地址："
    print_info "   - API文档: http://localhost:8000/docs"
    print_info "   - ReDoc: http://localhost:8000/redoc"
    print_info "   - 健康检查: http://localhost:8000/health"
    print_info ""
    print_info "🔑 默认管理员账号："
    print_info "   - 用户名: admin"
    print_info "   - 密码: admin123"
    print_info ""
    print_info "📊 查看日志: ./docker-start.sh logs"
}

# 停止服务
stop_services() {
    print_info "正在停止Vibe Cook Backend服务..."

    if docker compose version &> /dev/null; then
        docker compose down
    else
        docker-compose down
    fi

    print_info "✅ 服务已停止"
}

# 重启服务
restart_services() {
    print_info "正在重启Vibe Cook Backend服务..."
    stop_services
    sleep 2
    start_services
}

# 查看日志
view_logs() {
    print_info "查看服务日志（按Ctrl+C退出）..."

    if docker compose version &> /dev/null; then
        docker compose logs -f
    else
        docker-compose logs -f
    fi
}

# 检查服务状态
check_status() {
    print_info "服务状态："

    if docker compose version &> /dev/null; then
        docker compose ps
    else
        docker-compose ps
    fi

    print_info ""
    print_info "容器健康状态："
    docker ps --filter "name=app_" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# 初始化管理员账号
init_admin() {
    print_info "正在初始化管理员账号..."

    if docker compose version &> /dev/null; then
        docker compose exec backend python init_admin.py
    else
        docker-compose exec backend python init_admin.py
    fi

    print_info "✅ 管理员账号初始化完成"
    print_info "   - 用户名: admin"
    print_info "   - 密码: admin123"
}

# 进入容器shell
enter_shell() {
    print_info "进入backend容器shell..."

    if docker compose version &> /dev/null; then
        docker compose exec backend /bin/bash
    else
        docker-compose exec backend /bin/bash
    fi
}

# 清理所有数据（危险操作）
clean_all() {
    print_warn "⚠️  警告：此操作将删除所有数据（数据库、日志）"
    read -p "确认删除所有数据？(yes/no): " confirm

    if [ "$confirm" = "yes" ]; then
        print_info "正在清理所有数据..."

        if docker compose version &> /dev/null; then
            docker compose down -v
        else
            docker-compose down -v
        fi

        rm -rf data/logs/*
        print_info "✅ 数据清理完成"
    else
        print_info "取消清理操作"
    fi
}

# 显示帮助信息
show_help() {
    echo "Vibe Cook Backend - Docker 一键启动脚本"
    echo ""
    echo "使用方法: ./docker-start.sh [命令]"
    echo ""
    echo "可用命令："
    echo "  start       启动所有服务（默认）"
    echo "  stop        停止所有服务"
    echo "  restart     重启所有服务"
    echo "  logs        查看服务日志"
    echo "  status      查看服务状态"
    echo "  init-admin  初始化管理员账号"
    echo "  shell       进入backend容器shell"
    echo "  clean       清理所有数据（危险操作）"
    echo "  help        显示此帮助信息"
    echo ""
    echo "示例："
    echo "  ./docker-start.sh start"
    echo "  ./docker-start.sh logs"
    echo "  ./docker-start.sh status"
}

# 主函数
main() {
    # 检查Docker
    check_docker

    # 检查配置文件
    check_config

    # 解析命令
    case "${1:-start}" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            view_logs
            ;;
        status)
            check_status
            ;;
        init-admin)
            init_admin
            ;;
        shell)
            enter_shell
            ;;
        clean)
            clean_all
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
