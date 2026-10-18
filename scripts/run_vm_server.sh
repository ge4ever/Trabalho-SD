#!/usr/bin/env bash
# ==============================================================================
# Script de Deploy e Execução - VM-Server (API Gateway REST & Frontend Web)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=================================================================="
echo " [VM-SERVER] Preparando ambiente do API Gateway REST & Frontend..."
echo " Diretório base: $REPO_DIR"
echo "=================================================================="

# 1. Carregar .env se existir
if [ -f ".env" ]; then
    echo "[*] Carregando variáveis do arquivo .env..."
    set -a
    source .env
    set +a
fi

# 2. Instalar dependências de sistema se necessário
echo "[*] Verificando dependências do sistema (python3-venv, pip, tmux)..."
if ! dpkg -s python3-venv python3-pip tmux >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y python3-venv python3-pip tmux
fi

# 3. Configurar o ambiente virtual Python
if [ ! -d ".venv" ]; then
    echo "[*] Criando ambiente virtual Python (.venv)..."
    python3 -m venv .venv
fi

echo "[*] Ativando .venv e instalando dependências do requirements.txt..."
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# 4. Configuração do IP do Backend gRPC
if [ -z "$BACKEND_HOST" ]; then
    if [ -t 0 ]; then
        echo ""
        echo "------------------------------------------------------------------"
        echo " [CONFIGURAÇÃO] Informe o IP interno da máquina de Backend"
        echo " (Pressione ENTER para manter o padrão [10.128.0.3])"
        echo "------------------------------------------------------------------"
        read -p " IP Interno da VM-client [10.128.0.3]: " input_backend
        BACKEND_HOST="${input_backend:-10.128.0.3}"
    else
        BACKEND_HOST="10.128.0.3"
    fi
fi

export BACKEND_HOST="${BACKEND_HOST:-10.128.0.3}"

# 5. Encerrar sessões antigas se já estiverem em execução
if tmux has-session -t sd_gateway 2>/dev/null; then
    echo "[!] Encerrando sessão anterior 'sd_gateway' no tmux..."
    tmux kill-session -t sd_gateway
fi

# Liberar porta 50051 caso esteja presa
fuser -k 50051/tcp >/dev/null 2>&1 || true

# 6. Iniciar o Gateway no tmux
echo "[*] Iniciando API Gateway REST na porta 50051 via tmux..."

tmux new-session -d -s sd_gateway -n "gateway" \
  "source .venv/bin/activate && export BACKEND_HOST='$BACKEND_HOST' && python gateway/server.py"

sleep 2

# Tenta obter o IP público da VM atual para montar o link final
PUBLIC_IP=$(curl -s -m 2 ifconfig.me 2>/dev/null || echo "<IP_EXTERNO_DESTA_VM>")

echo "=================================================================="
echo " [SUCESSO] API Gateway e Frontend ATIVOS no tmux ('sd_gateway')!"
echo " - Escutando na porta: 50051 (aceita requisições HTTP REST externas)"
echo " - Conectado ao Backend gRPC em: $BACKEND_HOST (Portas 50052 e 50053)"
echo ""
echo " Acesso externo pelo navegador:"
echo "   http://${PUBLIC_IP}:50051/"
echo ""
echo " Para acompanhar os logs em tempo real, use:"
echo "   tmux attach -t sd_gateway"
echo "   (Para sair do tmux sem fechar os serviços: Ctrl + B, depois D)"
echo "=================================================================="
