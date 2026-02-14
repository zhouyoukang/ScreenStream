#!/bin/bash

# ScreenStream API服务一键停止脚本

set -e

echo "🛑 停止ScreenStream API服务..."

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

# 停止服务函数
stop_service() {
    local service_name=$1
    local port=$2
    local pid_file="$LOG_DIR/${service_name}.pid"
    
    echo "🔄 停止 $service_name..."
    
    # 通过PID文件停止
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  停止进程 PID: $pid"
            kill "$pid" 2>/dev/null || true
            
            # 等待进程结束
            local count=0
            while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            # 强制结束
            if kill -0 "$pid" 2>/dev/null; then
                echo "  强制停止进程 PID: $pid"
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    fi
    
    # 通过端口停止
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "  停止占用端口 $port 的进程"
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
    fi
    
    echo "✅ $service_name 已停止"
}

# 停止所有服务
stop_service "gateway" 8080
stop_service "mjpeg-server" 8081
stop_service "rtsp-server" 8082
stop_service "webrtc-server" 8083
stop_service "input-server" 8084

# 清理日志文件 (可选)
if [ "$1" = "--clean" ]; then
    echo "🧹 清理日志文件..."
    rm -f "$LOG_DIR"/*.log
    echo "✅ 日志文件已清理"
fi

echo ""
echo "🎉 所有ScreenStream API服务已停止"
