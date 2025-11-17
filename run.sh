#!/bin/bash

# AI Avatar 启动脚本
# 用法: ./run.sh [avatar_id] [port]
# avatar_id: wav2lip_avatar_female_model(默认) | wav2lip_avatar_glass_man | wav2lip_avatar_long_hair_girl
# port: 端口号(默认8010)

set -e

# 默认参数
AVATAR_ID=${1:-"wav2lip_avatar_female_model"}
PORT=${2:-8010}

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║           AI Avatar 数字人             ║"
echo "║        实时交互流式数字人系统           ║"
echo "║                                       ║"
echo "║  🤖 支持wav2lip数字人模型                 ║"
echo "║  🎤 支持声音克隆                       ║"
echo "║  💬 支持实时对话                       ║"
echo "║  📹 支持WebRTC视频输出                 ║"
echo "║                                       ║"
echo "║  首次运行会自动下载必要文件             ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

# 检查虚拟环境（可选）
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✓ 检测到虚拟环境: $VIRTUAL_ENV${NC}"
else
    echo -e "${YELLOW}⚠ 建议使用虚拟环境运行${NC}"
fi

echo -e "${GREEN}启动配置:${NC}"
echo -e "  数字人形象: ${AVATAR_ID}"
echo -e "  Web端口: ${PORT}"
echo -e "  访问地址: http://127.0.0.1:${PORT}/index.html"
echo ""

# # 检查依赖
# if [ -f "requirements.txt" ]; then
#     echo -e "${YELLOW}检查依赖...${NC}"
#     python3 -c "import torch, aiohttp, flask" 2>/dev/null || {
#         echo -e "${RED}缺少依赖包，请运行: pip install -r requirements.txt${NC}"
#         exit 1
#     }
#     echo -e "${GREEN}✓ 依赖检查通过${NC}"
# fi

echo -e "${BLUE}正在启动服务...${NC}"
echo "按 Ctrl+C 停止服务"
echo ""

# 启动应用
python3 main.py --avatar_id "$AVATAR_ID" --port "$PORT"