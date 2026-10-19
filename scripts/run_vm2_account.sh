#!/usr/bin/env bash
# ==============================================================================
# Script de Deploy e Execução - VM 2 (AccountService gRPC)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=================================================================="
echo " [VM 2 - ACCOUNTSERVICE] Preparando ambiente do serviço de Contas..."
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
    print('    Lembre-se de adicionar o IP externo desta VM (VM 2) nas Redes Autorizadas do Cloud SQL.')
" || true

# 6. Encerrar sessões antigas se já estiverem em execução
if tmux has-session -t sd_account 2>/dev/null; then
    echo "[!] Encerrando sessão anterior 'sd_account' no tmux..."
    tmux kill-session -t sd_account
fi

# Liberar porta 50052 caso esteja presa
fuser -k 50052/tcp >/dev/null 2>&1 || true

# 7. Iniciar o AccountService no tmux
echo "[*] Iniciando AccountService em background via tmux na porta 50052..."

tmux new-session -d -s sd_account -n "account-service" \
  "source .venv/bin/activate && export DB_HOST='$DB_HOST' DB_PORT='$DB_PORT' DB_NAME='$DB_NAME' DB_USER='$DB_USER' DB_PASSWORD='$DB_PASSWORD' && python account-service/account_server.py"

sleep 2

echo "=================================================================="
echo " [SUCESSO] Microsserviço AccountService ATIVO no tmux ('sd_account')!"
echo " - Escutando em: 0.0.0.0:50052 (aceita chamadas gRPC do Gateway e PixService)"
echo " - Banco Cloud SQL: $DB_HOST:$DB_PORT/$DB_NAME (Usuário: $DB_USER)"
echo ""
echo " Para acompanhar os logs das requisições na VM 2, use:"
echo "   tmux attach -t sd_account"
echo "   (Para sair do tmux sem fechar o serviço: Ctrl + B, depois D)"
echo "=================================================================="
