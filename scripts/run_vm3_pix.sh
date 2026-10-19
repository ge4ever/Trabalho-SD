#!/usr/bin/env bash
# ==============================================================================
# Script de Deploy e Execução - VM 3 (PixService gRPC)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=================================================================="
echo " [VM 3 - PIXSERVICE] Preparando ambiente do serviço de Pix..."
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

# 5. Configuração do endereço da VM 2 (AccountService)
if [ -z "$ACCOUNT_SERVICE_HOST" ]; then
    if [ -t 0 ]; then
        echo "------------------------------------------------------------------"
        read -p " IP Interno da VM 2 (AccountService) [10.128.0.3]: " input_acc
        ACCOUNT_SERVICE_HOST="${input_acc:-10.128.0.3}"
    else
        ACCOUNT_SERVICE_HOST="10.128.0.3"
    fi
fi

[[ "$ACCOUNT_SERVICE_HOST" != *":"* ]] && ACCOUNT_SERVICE_HOST="${ACCOUNT_SERVICE_HOST}:50052"

export DB_HOST="${DB_HOST:-35.202.26.114}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-banco_sd}"
export DB_USER="${DB_USER:-sd_user}"
export DB_PASSWORD="${DB_PASSWORD:-sd_password}"
export ACCOUNT_SERVICE_HOST

# 6. Testes rápidos de conectividade TCP
echo "[*] Verificando conectividade TCP com Cloud SQL ($DB_HOST:$DB_PORT)..."
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
    print('    Lembre-se de adicionar o IP externo desta VM (VM 3) nas Redes Autorizadas do Cloud SQL.')
" || true

echo "[*] Verificando comunicação gRPC com VM 2 ($ACCOUNT_SERVICE_HOST)..."
python3 -c "
import socket
host, port = '$ACCOUNT_SERVICE_HOST'.split(':')
s = socket.socket()
s.settimeout(4)
try:
    s.connect((host, int(port)))
    s.close()
    print('    [OK] Porta gRPC do AccountService na VM 2 alcançada com sucesso!')
except Exception as e:
    print('    [AVISO] Não foi possível alcançar VM 2 em $ACCOUNT_SERVICE_HOST: ' + str(e))
    print('    Certifique-se de que a VM 2 já esteja rodando o AccountService na mesma VPC.')
" || true

# 7. Encerrar sessões antigas se já estiverem em execução
if tmux has-session -t sd_pix 2>/dev/null; then
    echo "[!] Encerrando sessão anterior 'sd_pix' no tmux..."
    tmux kill-session -t sd_pix
fi

# Liberar porta 50053 caso esteja presa
fuser -k 50053/tcp >/dev/null 2>&1 || true

# 8. Iniciar o PixService no tmux
echo "[*] Iniciando PixService em background via tmux na porta 50053..."

tmux new-session -d -s sd_pix -n "pix-service" \
  "source .venv/bin/activate && export DB_HOST='$DB_HOST' DB_PORT='$DB_PORT' DB_NAME='$DB_NAME' DB_USER='$DB_USER' DB_PASSWORD='$DB_PASSWORD' ACCOUNT_SERVICE_HOST='$ACCOUNT_SERVICE_HOST' && python pix-service/pix_server.py"

sleep 2

echo "=================================================================="
echo " [SUCESSO] Microsserviço PixService ATIVO no tmux ('sd_pix')!"
echo " - Escutando em: 0.0.0.0:50053 (aceita chamadas gRPC do Gateway)"
echo " - Conectado ao AccountService (VM 2) em: $ACCOUNT_SERVICE_HOST"
echo " - Banco Cloud SQL: $DB_HOST:$DB_PORT/$DB_NAME (Usuário: $DB_USER)"
echo ""
echo " Para acompanhar os logs de transferências Pix na VM 3, use:"
echo "   tmux attach -t sd_pix"
echo "   (Para sair do tmux sem fechar o serviço: Ctrl + B, depois D)"
echo "=================================================================="
