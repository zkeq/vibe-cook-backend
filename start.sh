#!/bin/bash
# Vibe Cook Backend 快速启动脚本

echo "================================"
echo "Vibe Cook Backend 启动脚本"
echo "================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3"
    exit 1
fi

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo "⚠️  警告: config.yaml 不存在,从示例复制..."
    cp config.example.yaml config.yaml
    echo "✅ 已创建 config.yaml,请编辑配置后重新运行"
    exit 0
fi

# 检查依赖
echo "📦 检查依赖..."
pip3 list | grep -q fastapi
if [ $? -ne 0 ]; then
    echo "📥 安装依赖..."
    pip3 install -r requirements.txt
fi

# 启动服务
echo ""
echo "🚀 启动服务..."
echo ""
python3 main.py
