#!/usr/bin/env bash
# ==============================================================================
# Script de Execução Local - Trabalho-SD (Ambiente de Desenvolvimento)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

export LOCAL=1
export ACCOUNT_SERVICE_HOST="localhost:50052"
export PIX_SERVICE_HOST="localhost:50053"

if [ "$1" == "stop" ]; then
    echo "=================================================================="
    echo " [*] Encerrando serviços locais do Trabalho-SD..."
    echo "=================================================================="
    if command -v tmux >/dev/null 2>&1 && tmux has-session -t sd_local 2>/dev/null; then
        tmux kill-session -t sd_local
        echo "[*] Sessão tmux 'sd_local' finalizada."
    fi
    fuser -k 50051/tcp 50052/tcp 50053/tcp >/dev/null 2>&1 || true
    echo "[*] Portas 50051, 50052 e 50053 liberadas."
    echo "[*] Todos os serviços locais foram encerrados."
    exit 0
fi

echo "=================================================================="
echo " [DESENVOLVIMENTO LOCAL] Iniciando ecossistema de microsserviços"
echo " Diretório base: $REPO_DIR"
echo "=================================================================="

# 1. Configurar o ambiente virtual Python se necessário
if [ ! -d ".venv" ]; then
    echo "[*] Criando ambiente virtual Python (.venv)..."
    python3 -m venv .venv
fi

echo "[*] Ativando .venv e verificando dependências..."
source .venv/bin/activate
pip install -r requirements.txt --quiet

# 2. Compilar Protocol Buffers gRPC se necessário
echo "[*] Compilando arquivos gRPC do Protocol Buffers..."
python -m grpc_tools.protoc -I proto --python_out=grpc-generated --grpc_python_out=grpc-generated proto/pix.proto

# 3. Liberar portas se já estiverem ocupadas
echo "[*] Verificando e liberando portas (50051, 50052, 50053)..."
if command -v tmux >/dev/null 2>&1 && tmux has-session -t sd_local 2>/dev/null; then
    tmux kill-session -t sd_local
fi
fuser -k 50051/tcp 50052/tcp 50053/tcp >/dev/null 2>&1 || true

# 4. Iniciar os serviços
if command -v tmux >/dev/null 2>&1; then
    echo "[*] Iniciando serviços em segundo plano via tmux ('sd_local')..."
    
    # Inicia sessão com AccountService na janela 0
    tmux new-session -d -s sd_local -n "account" \
      "source .venv/bin/activate && export LOCAL=1 && python account-service/account_server.py"

    sleep 1

    # Cria janela 1 para PixService
    tmux new-window -t sd_local -n "pix" \
      "source .venv/bin/activate && export LOCAL=1 ACCOUNT_SERVICE_HOST='localhost:50052' && python pix-service/pix_server.py"

    sleep 1

    # Cria janela 2 para API Gateway
    tmux new-window -t sd_local -n "gateway" \
      "source .venv/bin/activate && export LOCAL=1 ACCOUNT_SERVICE_HOST='localhost:50052' PIX_SERVICE_HOST='localhost:50053' && python gateway/server.py"

    sleep 2
else
    echo "[*] tmux não encontrado, iniciando serviços em background..."
    source .venv/bin/activate
    export LOCAL=1
    python account-service/account_server.py > /tmp/sd_account.log 2>&1 &
    sleep 1
    python pix-service/pix_server.py > /tmp/sd_pix.log 2>&1 &
    sleep 1
    python gateway/server.py > /tmp/sd_gateway.log 2>&1 &
    sleep 2
fi

echo "=================================================================="
echo " [SUCESSO] Todos os serviços locais estão em execução!"
echo ""
echo " - AccountService (gRPC) : porta 50052"
echo " - PixService    (gRPC) : porta 50053"
echo " - API Gateway   (REST) : porta 50051"
echo " - Banco de dados       : SQLite local (database/banco_sd.db)"
echo "                          (ou PostgreSQL se configurado)"
echo ""
echo " Acessos disponíveis:"
echo "   Interface Web : http://localhost:50051/"
echo "   Cliente CLI   : python client/client.py bob@pix.local 50.00"
echo "   Rodar Testes  : pytest -v tests/test_flow.py"
echo ""
if command -v tmux >/dev/null 2>&1; then
    echo " Para monitorar os logs no tmux:"
    echo "   tmux attach -t sd_local"
    echo "   (Navegue entre abas: Ctrl+B depois 0, 1 ou 2. Para desanexar: Ctrl+B depois D)"
    echo ""
fi
echo " Para encerrar todos os serviços locais:"
echo "   ./scripts/run_local.sh stop"
echo "=================================================================="
