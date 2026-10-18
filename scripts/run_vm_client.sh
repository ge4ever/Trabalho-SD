#!/usr/bin/env bash
# ==============================================================================
# Script de Deploy e Execução - VM-Client (Nó de Backend gRPC)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=================================================================="
echo " [VM-CLIENT] Preparando ambiente dos Microsserviços gRPC..."
echo " Diretório base: $REPO_DIR"
echo "=================================================================="

# 1. Instalar dependências de sistema se necessário
echo "[*] Verificando dependências do sistema (python3-venv, pip, tmux)..."
if ! dpkg -s python3-venv python3-pip tmux >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y python3-venv python3-pip tmux
fi

# 2. Configurar o ambiente virtual Python
if [ ! -d ".venv" ]; then
    echo "[*] Criando ambiente virtual Python (.venv)..."
    python3 -m venv .venv
fi

echo "[*] Ativando .venv e instalando dependências do requirements.txt..."
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# 3. Encerrar sessões antigas se já estiverem em execução
if tmux has-session -t sd_backend 2>/dev/null; then
    echo "[!] Encerrando sessão anterior 'sd_backend' no tmux..."
    tmux kill-session -t sd_backend
fi

# Liberar portas 50052 e 50053 caso estejam presas
fuser -k 50052/tcp >/dev/null 2>&1 || true
fuser -k 50053/tcp >/dev/null 2>&1 || true

# 4. Variáveis de Conexão com o Cloud SQL
export DB_HOST="${DB_HOST:-35.202.26.114}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-banco_sd}"
export DB_USER="${DB_USER:-sd_user}"
export DB_PASSWORD="${DB_PASSWORD:-sd_password}"

# 5. Iniciar os serviços no tmux
echo "[*] Iniciando AccountService e PixService em background via tmux..."

# Janela 1: AccountService (porta 50052)
tmux new-session -d -s sd_backend -n "account-service" \
  "source .venv/bin/activate && export DB_HOST='$DB_HOST' DB_PORT='$DB_PORT' DB_NAME='$DB_NAME' DB_USER='$DB_USER' DB_PASSWORD='$DB_PASSWORD' && python account-service/account_server.py"

# Janela 2: PixService (porta 50053)
tmux new-window -t sd_backend:1 -n "pix-service" \
  "source .venv/bin/activate && export DB_HOST='$DB_HOST' DB_PORT='$DB_PORT' DB_NAME='$DB_NAME' DB_USER='$DB_USER' DB_PASSWORD='$DB_PASSWORD' && python pix-service/pix_server.py"

sleep 2

echo "=================================================================="
echo " [SUCESSO] Microsserviços de Backend ATIVOS no tmux ('sd_backend')!"
echo " - AccountService escutando em: 0.0.0.0:50052"
echo " - PixService escutando em:     0.0.0.0:50053"
echo " - Banco Cloud SQL configurado: $DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo " Para acompanhar os logs em tempo real, use:"
echo "   tmux attach -t sd_backend"
echo "   (Para sair do tmux sem fechar os serviços: Ctrl + B, depois D)"
echo "=================================================================="
