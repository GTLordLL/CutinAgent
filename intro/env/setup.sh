#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# CutinAgent (千务小切) — 一键环境配置脚本
# 适用: Ubuntu 24.04 + NVIDIA GPU + Docker
# 注意: 本脚本仅修改项目目录内文件，绝不污染用户系统环境
# ============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${RED}[WARN]${NC}  $*"; }
step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
OLLAMA="docker exec cutin-ollama ollama"
TMP_MODELFILE="/tmp/cutin_agent_qwen3_8k.Modelfile"

# ---- 清理函数 ----
cleanup() {
    rm -f "$TMP_MODELFILE"
}
trap cleanup EXIT

handle_error() {
    warn "配置过程中断 (第 $1 步失败)"
    warn "已尝试清理失败的中间产物:"
    # 清理可能残留在 /tmp 的 Modelfile
    rm -f "$TMP_MODELFILE"
    # 提醒用户注意可能残留的资源
    echo "  - 临时文件: $TMP_MODELFILE (已清理)"
    echo "  - Docker 容器 cutin-ollama 若已启动则保留，可复用"
    echo "  - 如需完全卸载: docker compose down -v"
    exit 1
}
trap 'handle_error ${LINENO:-?}' ERR

echo "=============================================="
echo " CutinAgent 环境自动配置"
echo "=============================================="
echo ""

# ---- 1/6 依赖检查 ----
step "1/6 检查系统依赖..."

if ! command -v docker &>/dev/null; then
    warn "未检测到 Docker，请先安装 Docker Engine:"
    warn "  https://docs.docker.com/engine/install/ubuntu/"
    exit 1
fi
info "Docker: $(docker --version)"

if ! docker compose version &>/dev/null; then
    warn "未检测到 Docker Compose 插件，请安装:"
    warn "  sudo apt install docker-compose-plugin"
    exit 1
fi
info "Docker Compose: $(docker compose version --short)"

if ! command -v nvidia-smi &>/dev/null; then
    warn "未检测到 nvidia-smi，请先安装 NVIDIA 驱动:"
    warn "  sudo apt install nvidia-driver-550"
    exit 1
fi
info "NVIDIA: $(nvidia-smi --query-gpu=name --format=csv,noheader)"

if ! dpkg -l nvidia-container-toolkit &>/dev/null 2>&1; then
    warn "未检测到 NVIDIA Container Toolkit，请安装:"
    warn "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html"
    exit 1
fi
info "NVIDIA Container Toolkit: 已安装"

if ! command -v python3 &>/dev/null; then
    warn "未检测到 Python3"
    exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$(python3 -c 'import sys; print(sys.version_info >= (3,10))')" != "True" ]]; then
    warn "Python 版本需要 >= 3.10，当前: $PY_VER"
    exit 1
fi
info "Python: $PY_VER"

echo ""

# ---- 2/6 启动 Ollama 容器 ----
step "2/6 启动 Ollama 容器..."
cd "$COMPOSE_DIR"

if docker ps --format '{{.Names}}' | grep -q '^cutin-ollama$'; then
    info "Ollama 容器已运行，跳过启动"
else
    docker compose up -d
    info "等待 Ollama 就绪（最多 30 秒）..."
    for i in $(seq 1 30); do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        warn "Ollama 启动超时，请检查: docker compose logs ollama"
        exit 1
    fi
fi
info "Ollama 已就绪 (http://localhost:11434)"

echo ""

# ---- 3/6 拉取基础模型 ----
step "3/6 拉取基础模型 qwen3:4b-instruct..."

if $OLLAMA list | grep -q 'qwen3:4b-instruct'; then
    info "模型 qwen3:4b-instruct 已存在，跳过拉取"
else
    info "正在从 Ollama 仓库拉取 (约 2.5 GB，取决于网速)..."
    $OLLAMA pull qwen3:4b-instruct
fi

echo ""

# ---- 4/6 创建定制模型 ----
step "4/6 创建定制模型 qwen3:4b-instruct_8k..."

if $OLLAMA list | grep -q 'qwen3:4b-instruct_8k'; then
    info "模型 qwen3:4b-instruct_8k 已存在，跳过创建"
else
    # num_ctx=8192  扩展上下文窗口，满足长 Prompt 需求
    # num_gpu=40    将全部模型层加载到 GPU（qwen3 4B 约 36 层），RTX 3060 6GB 实测 ~45 tok/s
    #               显存较小的 GPU 可适当减小此值，让部分层回退 CPU
    cat > "$TMP_MODELFILE" << 'MODELFILE'
FROM qwen3:4b-instruct
TEMPLATE "{{ .Prompt }}"
PARAMETER num_ctx 8192
PARAMETER num_gpu 40
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
MODELFILE

    info "正在创建定制模型..."
    if ! $OLLAMA create qwen3:4b-instruct_8k -f "$TMP_MODELFILE"; then
        warn "模型创建失败，已清理临时文件"
        rm -f "$TMP_MODELFILE"
        exit 1
    fi
    rm -f "$TMP_MODELFILE"
    info "定制模型创建成功"
fi

echo ""
info "已安装模型:"
$OLLAMA list
echo ""

# ---- 5/6 Python 虚拟环境 ----
step "5/6 配置 Python 虚拟环境..."

VENV_DIR="$COMPOSE_DIR/.venv"
VENV_CREATED=false

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    VENV_CREATED=true
    info "虚拟环境已创建: $VENV_DIR"
else
    info "虚拟环境已存在: $VENV_DIR，跳过创建"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

info "安装 Python 依赖..."
if ! pip install -q -r requirements.txt; then
    warn "依赖安装失败"
    if [ "$VENV_CREATED" = true ]; then
        warn "已清理新建的虚拟环境: $VENV_DIR"
        rm -rf "$VENV_DIR"
    fi
    exit 1
fi
info "Python 依赖安装完成"

echo ""

# ---- 6/6 完成 ----
step "6/6 环境配置完成!"
echo ""
echo "=============================================="
echo " CutinAgent 环境就绪"
echo "=============================================="
echo ""
echo "  Ollama    : http://localhost:11434"
echo "  定制模型  : qwen3:4b-instruct_8k (ctx=8192)"
echo "  Python    : $(python3 --version)"
echo ""
echo "  启动项目:"
echo "    source .venv/bin/activate"
echo "    python main.py"
echo ""
echo "  管理模型 (如有其他模型需求):"
echo "    docker exec -it cutin-ollama ollama pull <model>"
echo ""
echo "  卸载 (删除容器 + 数据卷):"
echo "    docker compose down -v"
echo ""
