#!/bin/bash

# ScreenStream API服务一键启动脚本
# 用于本地开发和测试环境

set -e

echo "🚀 启动ScreenStream API服务..."

# 检查Java环境
if ! command -v java &> /dev/null; then
    echo "❌ Java未安装，请先安装JDK 17+"
    exit 1
fi

JAVA_VERSION=$(java -version 2>&1 | head -n 1 | cut -d'"' -f2 | cut -d'.' -f1)
if [ "$JAVA_VERSION" -lt "17" ]; then
    echo "❌ Java版本过低，需要JDK 17+，当前版本: $JAVA_VERSION"
    exit 1
fi

echo "✅ Java版本检查通过: $JAVA_VERSION"

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_DIR="$PROJECT_DIR/api-services"
LOG_DIR="$PROJECT_DIR/logs"

# 创建日志目录
mkdir -p "$LOG_DIR"

# JAR文件路径
GATEWAY_JAR="$API_DIR/gateway/build/libs/gateway-2.0.0.jar"
MJPEG_JAR="$API_DIR/mjpeg-server/build/libs/mjpeg-server-2.0.0.jar"
RTSP_JAR="$API_DIR/rtsp-server/build/libs/rtsp-server-2.0.0.jar"
WEBRTC_JAR="$API_DIR/webrtc-server/build/libs/webrtc-server-2.0.0.jar"
INPUT_JAR="$API_DIR/input-server/build/libs/input-server-2.0.0.jar"

# 检查JAR文件是否存在
check_jar() {
    if [ ! -f "$1" ]; then
        echo "❌ JAR文件不存在: $1"
        echo "请先运行构建: ./gradlew build"
        exit 1
    fi
}

echo "📦 检查JAR文件..."
check_jar "$GATEWAY_JAR"
check_jar "$MJPEG_JAR"
check_jar "$RTSP_JAR"
check_jar "$WEBRTC_JAR"
check_jar "$INPUT_JAR"
echo "✅ 所有JAR文件检查完成"

# 启动服务函数
start_service() {
    local service_name=$1
    local jar_path=$2
    local port=$3
    local pid_file="$LOG_DIR/${service_name}.pid"
    local log_file="$LOG_DIR/${service_name}.log"
    
    echo "🔄 启动 $service_name (端口: $port)..."
    
    # 检查端口是否被占用
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  端口 $port 已被占用，尝试停止现有进程..."
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
    
    # 启动服务
    nohup java -jar -Xmx512m -Dserver.port=$port "$jar_path" > "$log_file" 2>&1 &
    local pid=$!
    echo $pid > "$pid_file"
    
    echo "✅ $service_name 已启动 (PID: $pid, 日志: $log_file)"
}

# 等待服务启动
wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    echo "⏳ 等待 $service_name 启动..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            echo "✅ $service_name 启动成功"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo ""
    echo "❌ $service_name 启动超时"
    return 1
}

# 清理函数
cleanup() {
    echo ""
    echo "🧹 清理进程..."
    
    for pid_file in "$LOG_DIR"/*.pid; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            local service_name=$(basename "$pid_file" .pid)
            
            if kill -0 "$pid" 2>/dev/null; then
                echo "停止 $service_name (PID: $pid)"
                kill "$pid"
            fi
            
            rm -f "$pid_file"
        fi
    done
    
    exit 1
}

# 捕获退出信号
trap cleanup EXIT INT TERM

# 启动所有服务
echo "🚀 开始启动服务..."

# 按顺序启动服务
start_service "input-server" "$INPUT_JAR" 8084
start_service "webrtc-server" "$WEBRTC_JAR" 8083  
start_service "rtsp-server" "$RTSP_JAR" 8082
start_service "mjpeg-server" "$MJPEG_JAR" 8081
start_service "gateway" "$GATEWAY_JAR" 8080

# 等待服务启动完成
echo ""
echo "⏳ 等待所有服务启动完成..."
sleep 5

wait_for_service "Input Server" "http://localhost:8084/health"
wait_for_service "WebRTC Server" "http://localhost:8083/health"  
wait_for_service "RTSP Server" "http://localhost:8082/health"
wait_for_service "MJPEG Server" "http://localhost:8081/health"
wait_for_service "Gateway" "http://localhost:8080/health"

echo ""
echo "🎉 所有服务启动完成！"
echo ""
echo "📊 服务状态:"
echo "  Gateway:    http://localhost:8080"
echo "  MJPEG:      http://localhost:8081" 
echo "  RTSP:       http://localhost:8082"
echo "  WebRTC:     http://localhost:8083"
echo "  Input:      http://localhost:8084"
echo ""
echo "📖 快速测试:"
echo "  curl http://localhost:8080/status"
echo "  curl -X POST http://localhost:8080/start-all"
echo ""
echo "📝 日志位置: $LOG_DIR"
echo "🛑 停止服务: ./scripts/stop-all.sh"
echo ""

# 显示服务状态
echo "🔍 获取服务状态..."
curl -s http://localhost:8080/status | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print('服务运行状态:')
    for name, service in data.get('services', {}).items():
        status = '✅ 健康' if service.get('isHealthy', False) else '❌ 异常'
        print(f'  {name.upper()}: {status} (响应时间: {service.get(\"responseTime\", 0)}ms)')
except:
    print('无法获取详细状态')
"

echo ""
echo "🎯 服务已就绪，可以开始测试！"
echo "按 Ctrl+C 停止所有服务"

# 保持脚本运行，直到收到停止信号
while true; do
    sleep 10
    
    # 检查关键服务是否还在运行
    if ! curl -s -f http://localhost:8080/health > /dev/null 2>&1; then
        echo "❌ Gateway服务异常，退出..."
        break
    fi
done
