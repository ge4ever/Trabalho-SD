# Contexto do Projeto e Histórico de Decisões de Arquitetura

Este documento registra o contexto completo das discussões, requisitos atendidos, decisões de arquitetura e o passo a passo para execução e deploy no Google Cloud Platform (GCP).

---

## 1. Contexto e Requisitos do Trabalho

O objetivo foi transformar a base inicial em uma **arquitetura de microsserviços distribuídos** aderente aos seguintes requisitos:

1. **Frontend:**
   - Interface visual funcional mobile-first / desktop que interage exclusivamente com o API Gateway (nunca gRPC direto no cliente).
   - Comunicação feita 100% via HTTP/REST JSON com envio do header `Authorization: Bearer <token>`.
2. **API Gateway (REST / HTTP):**
   - Ponto único de entrada implementado em Flask na porta `50051`.
   - Responsável por receber requisições HTTP/JSON, autenticar, validar payload e despachar para os serviços gRPC internos.
3. **Backend com no mínimo 2 Microsserviços internos gRPC:**
   - `AccountService` (porta `50052`): Gestão de contas, saldo, credenciais e operações atômicas de débito/crédito.
   - `PixService` (porta `50053`): Processamento transacional de transferências Pix, validação de regras de transferência, comunicação gRPC inter-serviços com AccountService e registro de histórico.
   - Comunicação interna baseada exclusivamente em chamadas remotas gRPC com Protocol Buffers binários.
4. **Banco de Dados Real (Sem Mocks):**
   - PostgreSQL operacional rodando via `docker-compose.yml` com tabelas reais `contas` e `transacoes`.
   - Zero mocks em memória: todas as consultas, débitos, créditos e inserções refletem no banco de dados.
   - Fallback automático para SQLite (`database/banco_sd.db`) caso o PostgreSQL não esteja rodando, mantendo persistência real em disco.
5. **Validação no Backend:**
   - Validação obrigatória do payload JSON no API Gateway para campos de negócio (`chave_origem`, `chave_destino`, `valor > 0`, etc.).
   - Respostas semânticas via HTTP Status Code: retorno explícito de `400 Bad Request` com lista detalhada de erros caso os dados sejam inválidos/ausentes e `201 Created` em caso de sucesso de transferência.
6. **Segurança (Autenticação JWT):**
   - Rota `POST /auth/login` gerando token JWT assinado (algoritmo HMAC-SHA256).
   - Middleware/decorator `@jwt_required` no API Gateway validando o cabeçalho `Authorization: Bearer <token>`.
   - Requisições sem token válido são imediatamente barradas na borda com `401 Unauthorized`.
7. **Tradução e Delegação de Protocolo:**
   - O API Gateway recebe JSON, desserializa, autentica/valida e serializa para gRPC/Protobuf binário, orquestrando o fluxo entre os microsserviços.

---

## 2. Estrutura de Arquivos do Projeto

```text
Trabalho-SD/
├── README.md                      # Documentação oficial do projeto
├── CONTEXTO_PROJETO.md            # Este arquivo de contexto detalhado
├── docker-compose.yml             # Orquestração do PostgreSQL operacional
├── requirements.txt               # Dependências Python (Flask, grpcio, PyJWT, psycopg2-binary, pytest)
├── proto/
│   └── pix.proto                  # Contratos gRPC atualizados (AccountService e PixService)
├── grpc-generated/                # Stubs Python compilados a partir do proto
│   ├── pix_pb2.py
│   └── pix_pb2_grpc.py
├── database/                      # Módulo de persistência real
│   ├── __init__.py
│   ├── db.py                      # Conector inteligente PostgreSQL (com fallback SQLite)
│   └── init.sql                   # DDL das tabelas 'contas' e 'transacoes' e seeds iniciais
├── gateway/                       # API Gateway REST (Borda) + Frontend
│   ├── __init__.py
│   ├── server.py                  # Flask REST na porta 50051 com JWT, validação 400/201 e gRPC
│   ├── static/                    # CSS e JavaScript do Frontend
│   │   ├── css/style.css
│   │   └── js/app.js              # Lógica com autenticação JWT e fetch REST autenticado
│   └── templates/
│       └── index.html             # Interface Web bancária Mobile-First
├── account-service/               # Microsserviço interno 1
│   └── account_server.py          # gRPC na porta 50052 conectado ao PostgreSQL
├── pix-service/                   # Microsserviço interno 2 (gRPC puro)
│   └── pix_server.py              # gRPC na porta 50053 (Transferências Pix)
├── client/
│   └── client.py                  # Cliente CLI REST com autenticação JWT
└── tests/
    └── test_flow.py               # Suíte de testes automatizados com pytest (100% verde)
```

---

## 3. Como Rodar Localmente

### 1. Iniciar o Banco de Dados (PostgreSQL)
```bash
docker-compose up -d
```

### 2. Ativar Ambiente Virtual e Dependências
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Iniciar os Serviços (3 Terminais)
- **Terminal 1 - AccountService (gRPC :50052):**
  ```bash
  python account-service/account_server.py
  ```
- **Terminal 2 - PixService (gRPC :50053):**
  ```bash
  python pix-service/pix_server.py
  ```
- **Terminal 3 - API Gateway REST (:50051):**
  ```bash
  python gateway/server.py
  ```

### 4. Acessar a Aplicação
- **Frontend Web:** `http://localhost:50051/`
- **Cliente CLI:**
  ```bash
  python client/client.py bob@pix.local 50.00
  ```
- **Rodar Testes Automatizados:**
  ```bash
  pytest -v tests/test_flow.py
  ```

---

## 4. Como Subir e Rodar no Google Cloud Platform (VM Compute Engine)

A aplicação já está pronta para a nuvem. Todas as portas escutam em `0.0.0.0` e os hosts são parametrizáveis.

### Passo 1: Criar Regra de Firewall no GCP
No console do Google Cloud (**Rede VPC** > **Regras de Firewall**):
- **Nome:** `allow-pix-gateway`
- **Destino:** Todas as instâncias na rede
- **IPs de Origem:** `0.0.0.0/0`
- **Protocolos e Portas:** `tcp:50051`

*(As portas 50052, 50053 e 5432 NÃO devem ser expostas na internet, pois são microsserviços internos).*

### Passo 2: Clonar e Rodar na VM via SSH
Conecte-se via SSH na VM do GCP:
```bash
git clone https://github.com/ge4ever/Trabalho-SD.git
cd Trabalho-SD
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker-compose up -d
```

### Passo 3: Executar em Background na VM (Evitar cair ao fechar SSH)
Instale o `tmux`:
```bash
sudo apt-get install -y tmux
tmux new -s pix_sistema
```
Inicie os 3 serviços em abas/janelas do tmux:
1. `python account-service/account_server.py`
2. `python pix-service/pix_server.py`
3. `python gateway/server.py`

Pressione `Ctrl + B` e depois tecla `D` para desanexar o tmux. Mesmo fechando o terminal SSH, os serviços continuarão ativos.

### Passo 4: Acessar Externamente
- **Frontend no Navegador:** `http://<IP_EXTERNO_DA_VM>:50051/`
- **CLI a partir do seu PC pessoal:**
  ```bash
  SERVER_HOST=<IP_EXTERNO_DA_VM> python client/client.py bob@pix.local 50.00
  ```

---

## 5. Arquitetura Distribuída em 2 VMs no GCP (Cenário de Produção Ativo)

Para atender a topologia de nós distribuídos no Google Cloud Platform com duas máquinas virtuais, o sistema foi organizado no modelo **Borda (Edge) vs Backend**:

```text
       [ Navegador Web / Cliente CLI ]
                      │
                      │ HTTP / REST :50051 (IP Público)
                      ▼
   ┌──────────────────────────────────────────────┐
   │  VM 1: vm-server (Gateway / Frontend)        │
   │  - Flask REST na porta 50051                 │
   │  - IP Interno: 10.128.0.2                    │
   │  - Autenticação JWT na borda                 │
   │  - Validação estrita de JSON (400)           │
   │  - Tradução REST/JSON <-> gRPC/Protobuf      │
   └──────────────────────┬───────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         │ gRPC :50052                     │ gRPC :50053
         ▼                                 ▼
   ┌──────────────────────────────────────────────┐
   │  VM 2: Backend (Account & Pix Services)      │
   │  - IP de Rede: 136.80.4.171                  │
   │  - AccountService (gRPC :50052)              │
   │  - PixService (gRPC :50053)                  │
   └──────────────────────┬───────────────────────┘
                          │
                          │ TCP SQL :5432
                          ▼
   ┌──────────────────────────────────────────────┐
   │  Banco de Dados Real (PostgreSQL)            │
   │  - Host: 35.202.26.114:5432                  │
   │  - Fallback automático para SQLite em disco  │
   └──────────────────────────────────────────────┘
```

### Tabela Consolidada de Portas e Serviços

| Porta | Componente | Protocolo | Host / Nó | Visibilidade GCP |
|---|---|---|---|---|
| **50051** | API Gateway (Flask) + Frontend | HTTP/REST | `vm-server` (`10.128.0.2`) | **Pública** (Liberada no Firewall para `0.0.0.0/0`) |
| **50052** | AccountService | gRPC (HTTP/2) | `136.80.4.171` | **Interna / VPC** |
| **50053** | PixService | gRPC (HTTP/2) | `136.80.4.171` | **Interna / VPC** |
| **5432** | PostgreSQL Operacional | TCP / SQL | `35.202.26.114` | **Interna / VPC** |

---

## 6. Histórico de Depuração: Resolução do Erro gRPC 503

### Problema Identificado
Durante a execução na nuvem, requisições de login no Gateway falhavam com `503 Service Unavailable`:
```text
[GATEWAY] Erro gRPC ao comunicar com AccountService no login:
status = StatusCode.UNAVAILABLE
details = "failed to connect to all addresses; last error: UNKNOWN: ipv4:136.80.4.171:50052: Failed to connect to remote host: Connection refused"
```

### Diagnóstico Técnico por Sondagem
Foi executado um teste de conectividade via socket para as portas em `136.80.4.171`:
- **Porta 50053 (`PixService`):** Retornou código `0` (conectado com sucesso).
- **Porta 50052 (`AccountService`):** Retornou código `111` (`Connection refused`).

**Conclusão:** O `PixService` estava em execução, mas o processo do `AccountService` não estava rodando na máquina `136.80.4.171` ou sofreu encerramento prévio.

### Melhorias e Ajustes Implementados no Código
1. **Configuração Automática de Hosts (`gateway/server.py`):**
   - Criação da função `resolve_service_host` com fallback inteligente para `136.80.4.171:50052` e `136.80.4.171:50053`.
   - Sanitização de URLs (remoção de `http://`, `https://` acidentais e inserção da porta padrão se omitida).
2. **Observabilidade e Logs em Tempo Real (`gateway/server.py`):**
   - Banner de inicialização exibindo os alvos gRPC configurados.
   - Logs descritivos a cada chamada: `[GATEWAY] [LOGIN]`, `[GATEWAY] [SALDO]`, `[GATEWAY] [PIX]`, etc.
   - Detalhamento de erros gRPC com status e mensagem amigável no retorno 503.
   - Inclusão de timeouts de 5s para evitar bloqueio indefinido de requisições.
3. **Prevenção de Falha Silenciosa de Vinculação de Porta (`account_server.py` e `pix_server.py`):**
   - Verificação explícita do retorno de `server.add_insecure_port(...)`. Caso a porta esteja ocupada ou inacessível (`bound_port == 0`), uma exceção com instruções de liberação (`fuser -k <porta>/tcp`) é disparada.
   - Banners de inicialização com confirmação de binding em `0.0.0.0` e driver de banco ativo.
4. **Resiliência do Banco de Dados (`database/db.py`):**
   - Configuração do host padrão para `35.202.26.114`.
   - Aumento do `connect_timeout` para 5 segundos.
   - Registro em log do erro de conexão caso o PostgreSQL esteja inacessível antes de acionar o fallback para SQLite.

---

## 7. Conformidade com Requisitos de Tradução e Delegação de Protocolo

A implementação atende com 100% de precisão ao fluxo exigido:
1. **Recebimento e Desserialização:** O Gateway recebe requisições HTTP REST via Flask e desserializa o corpo JSON com `request.get_json()`.
2. **Autenticação:** O decorator `@jwt_required` valida tokens `Authorization: Bearer <token>` com HMAC-SHA256 e barra acessos com `401 Unauthorized`.
3. **Validação:** Valida campos de negócio e devolve semântica `400 Bad Request` com lista de erros antes de acionar o backend.
4. **Serialização gRPC/Protobuf:** Instancia objetos de contrato binário (`pix_pb2.TransferenciaRequest`, `pix_pb2.AuthRequest`, etc.) e transmite via HTTP/2 binário para os microsserviços.
5. **Orquestração e Resposta:** O Gateway recebe as mensagens binárias gRPC, traduz de volta para JSON e responde com códigos semânticos (`200 OK`, `201 Created`, `400`, `401`, `503`).

