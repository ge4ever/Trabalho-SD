#!/usr/bin/env bash
# ==============================================================================
# Script de Deploy e Execução - VM 1 (API Gateway REST & Frontend Web)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=================================================================="
echo " [VM 1 - GATEWAY] Preparando ambiente do API Gateway REST..."
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

# 4. Configuração dos IPs de Backend gRPC (VM 2 e VM 3)
if [ -z "$ACCOUNT_SERVICE_HOST" ]; then
    if [ -t 0 ]; then
        echo ""
        echo "------------------------------------------------------------------"
        echo " [CONFIGURAÇÃO] Informe os IPs internos dos Microsserviços gRPC"
        echo " (Pressione ENTER para manter o padrão sugerido)"
        echo "------------------------------------------------------------------"
        read -p " IP Interno da VM 2 (AccountService) [10.128.0.3]: " input_acc
        ACCOUNT_SERVICE_HOST="${input_acc:-10.128.0.3}"
    else
        ACCOUNT_SERVICE_HOST="10.128.0.3"
    fi
fi

if [ -z "$PIX_SERVICE_HOST" ]; then
    if [ -t 0 ]; then
        read -p " IP Interno da VM 3 (PixService) [10.128.0.4]: " input_pix
        PIX_SERVICE_HOST="${input_pix:-10.128.0.4}"
    else
        PIX_SERVICE_HOST="10.128.0.4"
    fi
fi

# Formata com porta se omitida
[[ "$ACCOUNT_SERVICE_HOST" != *":"* ]] && ACCOUNT_SERVICE_HOST="${ACCOUNT_SERVICE_HOST}:50052"
[[ "$PIX_SERVICE_HOST" != *":"* ]] && PIX_SERVICE_HOST="${PIX_SERVICE_HOST}:50053"

export ACCOUNT_SERVICE_HOST
export PIX_SERVICE_HOST

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
  "source .venv/bin/activate && export ACCOUNT_SERVICE_HOST='$ACCOUNT_SERVICE_HOST' PIX_SERVICE_HOST='$PIX_SERVICE_HOST' && python gateway/server.py"

sleep 2

# Tenta obter o IP público da VM 1 para montar o link de acesso externo
PUBLIC_IP=$(curl -s -m 2 ifconfig.me 2>/dev/null || echo "<IP_EXTERNO_VM1>")

echo "=================================================================="
echo " [SUCESSO] API Gateway e Frontend ATIVOS no tmux ('sd_gateway')!"
echo " - Escutando na porta: 50051 (Interface Web e REST externa)"
echo " - AccountService alvo (VM 2): $ACCOUNT_SERVICE_HOST"
echo " - PixService alvo (VM 3):     $PIX_SERVICE_HOST"
echo ""
echo " Acesso externo pelo navegador:"
echo "   http://${PUBLIC_IP}:50051/"
echo ""
echo " Para acompanhar os logs em tempo real na VM 1, use:"
echo "   tmux attach -t sd_gateway"
echo "   (Para sair do tmux sem fechar o serviço: Ctrl + B, depois D)"
echo "=================================================================="
