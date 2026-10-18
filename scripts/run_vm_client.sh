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

# 4. Configuração das credenciais do Cloud SQL
if [ -z "$DB_HOST" ]; then
    if [ -t 0 ]; then
        echo ""
        echo "------------------------------------------------------------------"
        echo " [CONFIGURAÇÃO] Informe os dados da sua instância Cloud SQL"
        echo " (Pressione ENTER para manter o valor padrão exibido entre colchetes)"
        echo "------------------------------------------------------------------"
        read -p " IP Público do Cloud SQL [35.202.26.114]: " input_host
        DB_HOST="${input_host:-35.202.26.114}"

        read -p " Nome do Banco [banco_sd]: " input_name
        DB_NAME="${input_name:-banco_sd}"

        read -p " Usuário do PostgreSQL [sd_user]: " input_user
        DB_USER="${input_user:-sd_user}"

        read -s -p " Senha do PostgreSQL [sd_password]: " input_pass
        echo ""
        DB_PASSWORD="${input_pass:-sd_password}"
    else
        DB_HOST="35.202.26.114"
    fi
fi

export DB_HOST="${DB_HOST:-35.202.26.114}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-banco_sd}"
export DB_USER="${DB_USER:-sd_user}"
export DB_PASSWORD="${DB_PASSWORD:-sd_password}"

# 5. Teste rápido de conectividade na porta do PostgreSQL
echo "[*] Verificando conectividade TCP com $DB_HOST:$DB_PORT..."
python3 -c "
import socket
s = socket.socket()
s.settimeout(4)
try:
    s.connect(('$DB_HOST', int('$DB_PORT')))
    s.close()
    print('    [OK] Conexão com Cloud SQL ($DB_HOST:$DB_PORT) alcançada com sucesso!')
except Exception as e:
    print('    [AVISO] Não foi possível conectar a $DB_HOST:$DB_PORT: ' + str(e))
    print('    Lembre-se de adicionar o IP externo desta VM nas Redes Autorizadas do Cloud SQL.')
" || true

# 6. Encerrar sessões antigas se já estiverem em execução
if tmux has-session -t sd_backend 2>/dev/null; then
    echo "[!] Encerrando sessão anterior 'sd_backend' no tmux..."
    tmux kill-session -t sd_backend
fi

# Liberar portas 50052 e 50053 caso estejam presas
fuser -k 50052/tcp >/dev/null 2>&1 || true
fuser -k 50053/tcp >/dev/null 2>&1 || true

# 7. Iniciar os serviços no tmux
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
echo " - Banco Cloud SQL configurado: $DB_HOST:$DB_PORT/$DB_NAME (Usuário: $DB_USER)"
echo ""
echo " Para acompanhar os logs em tempo real, use:"
echo "   tmux attach -t sd_backend"
echo "   (Para alternar abas no tmux: Ctrl + B, depois N)"
echo "   (Para sair do tmux sem fechar os serviços: Ctrl + B, depois D)"
echo "=================================================================="
