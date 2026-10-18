# Trabalho 1 - Sistema Distribuído de Contas e Transações Pix

#### Participantes
- Geovana Ribeiro Araújo Espinosa - 202405104
- Dennis Lucas Gonçalves - 202400839
- Vitor Vittorete Serafim de Pina - 202405128

---

## Descrição do Projeto

O projeto consiste em um sistema distribuído de transações bancárias no estilo Pix, estruturado com **API Gateway (REST)**, **2 microsserviços internos (gRPC)** e **banco de dados relacional real (PostgreSQL)**, atendendo rigorosamente a todos os requisitos de arquitetura de microsserviços e segurança.

### Requisitos Atendidos:
1. **Frontend:** Interface visual funcional (Mobile-First / Desktop) consumindo **exclusivamente o API Gateway** via REST HTTP/JSON (nunca gRPC direto no cliente).
2. **API Gateway (REST / HTTP):** Ponto único de entrada implementado em Flask (porta `50051`), com validação de payload, autenticação JWT e tradução REST -> gRPC.
3. **Backend com 2 Microsserviços internos gRPC:**
   - `AccountService` (gRPC na porta `50052`): Gestão de contas, saldo, autenticação e débitos/créditos.
   - `PixService` (gRPC na porta `50053`): Processamento transacional de transferências e histórico.
   - Comunicação backend baseada em gRPC com Protocol Buffers binários.
4. **Banco de Dados Real (Sem Mocks):**
   - Conectado a PostgreSQL operacional (via `docker-compose.yml`) com tabelas reais `contas` e `transacoes`.
   - Todas as consultas, alterações de saldo e transferências refletem de fato no banco (zero mocks ou listas na memória).
   - Suporte a fallback automático em SQLite (`database/banco_sd.db`) caso o container não esteja em execução.
5. **Validação no Backend:** Validação obrigatória de dados de negócio no Gateway com retorno explícito de `400 Bad Request` para erros e `201 Created` para transferências realizadas.
6. **Segurança (Autenticação JWT):** Middleware de segurança no API Gateway exigindo `Authorization: Bearer <token>`. Bloqueio imediato na borda com `401 Unauthorized` se token inválido ou ausente.
7. **Tradução e Delegação de Protocolo:** Recebe JSON, desserializa, autentica, valida e serializa em chamadas gRPC/Protobuf binárias para os microsserviços internos.

---

## Arquitetura do Sistema

```text
       [ Frontend Web (Navegador) ]   ou   [ Cliente CLI ]
                          |
                          | HTTP/JSON (REST) + JWT Bearer Token
                          v
         ======================================
          API GATEWAY (Flask REST na porta 50051)
           - Ponto Único de Entrada
           - Middleware JWT (Barrar 401)
           - Validação de Payloads JSON (Barrar 400)
           - Tradução REST/JSON <-> gRPC/Protobuf
         ======================================
                 |                     |
   gRPC Protobuf | :50052              | gRPC Protobuf :50053
                 v                     v
         +----------------+    +-----------------------+
         | AccountService |    |      PixService       |
         |     (gRPC)     |    |        (gRPC)         |
         +----------------+    +-----------------------+
                 |                     |
                 +----------+----------+
                            |
                            v
               [ BANCO DE DADOS REAL ]
             PostgreSQL (ou SQLite local)
             - Tabela: 'contas'
             - Tabela: 'transacoes'
```

---

## Tabela de Componentes e Portas

| Componente | Porta | Protocolo | Responsabilidade |
|---|---|---|---|
| **API Gateway** | `50051` | HTTP / REST | Entrada única, Interface Web, rotas `/auth/login`, `/pix/transferir`, `/pix/saldo`, JWT e validação |
| **AccountService** | `50052` | gRPC | Microsserviço de contas: autenticação, consulta de saldo, débito e crédito no banco |
| **PixService** | `50053` | gRPC | Microsserviço de Pix: validação da transferência, orquestração e registro no banco |
| **PostgreSQL** | `5432` | TCP / SQL | Banco de dados relacional persistente com as tabelas `contas` e `transacoes` |
| **Client CLI** | - | HTTP / REST | Script de terminal cliente que autentica via JWT e envia requisições ao Gateway |

---

## Como Executar Localmente

### 1. Clonar e Instalar Dependências

```bash
git clone https://github.com/ge4ever/Trabalho-SD.git
cd Trabalho-SD
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Iniciar o Banco de Dados Real (PostgreSQL)

Suba o container do PostgreSQL com o Docker Compose:
```bash
docker-compose up -d
```
*(Nota: se preferir rodar sem Docker, o sistema utiliza automaticamente SQLite persistente em `database/banco_sd.db` sem perda de funcionalidade).*

### 3. Compilar os Protocol Buffers (gRPC)

```bash
python -m grpc_tools.protoc -I proto --python_out=grpc-generated --grpc_python_out=grpc-generated proto/pix.proto
```

### 4. Iniciar os Serviços (3 Terminais)

#### Terminal 1: Microsserviço 1 (AccountService gRPC)
```bash
source .venv/bin/activate
python account-service/account_server.py
```

#### Terminal 2: Microsserviço 2 (PixService gRPC)
```bash
source .venv/bin/activate
python pix-service/pix_server.py
```

#### Terminal 3: API Gateway REST
```bash
source .venv/bin/activate
python gateway/server.py
```

---

## Como Executar no Google Cloud Platform (GCP)

A aplicação está pronta para operar de forma distribuída em 2 Máquinas Virtuais (Compute Engine) integradas ao banco gerenciado **Google Cloud SQL (PostgreSQL)**.

> [!IMPORTANT]
> Ao criar as duas VMs no Compute Engine (Ubuntu 22.04+ ou Debian 11+), crie ambas na **mesma Região** (ex: `us-central1`) e na **mesma rede VPC** (`default`). Isso garante que a comunicação entre o Gateway e o Backend ocorra via **IP interno privado**, com altíssima velocidade, sem custos de saída e com segurança.

### Topologia de Nós

| Máquina / Instância | Papel no Sistema | IP Interno (VPC) | IP Externo (Público) | Portas Ativas |
|---|---|---|---|---|
| **VM-Server** | API Gateway (Flask REST) + Frontend Web | `<IP_INTERNO_VM_SERVER>` | `<IP_EXTERNO_VM_SERVER>` | `50051` (Pública) |
| **VM-client** | Backend gRPC (`AccountService` e `PixService`) | `<IP_INTERNO_VM_CLIENT>` | `<IP_EXTERNO_VM_CLIENT>` | `50052`, `50053` (VPC Interna) |
| **Cloud SQL** | Banco Relacional PostgreSQL | - | `<IP_PUBLICO_CLOUD_SQL>` | `5432` (Redes Autorizadas) |

---

### Passo 1: Configuração no Console do GCP

#### 1. Configurar o Cloud SQL (PostgreSQL)
1. **Criar a base de dados:**
   - No painel da sua instância Cloud SQL, vá no menu **Bancos de dados** > clique em **Criar banco de dados**.
   - Nome do banco: `banco_sd`.
2. **Criar o usuário do banco:**
   - No menu lateral **Usuários** > clique em **Adicionar conta de usuário**.
   - Usuário: `sd_user` | Senha: `sd_password` (ou a senha de sua preferência).
   *(As tabelas `contas` e `transacoes` e os saldos de teste são criados automaticamente pelo código na primeira conexão)*.
3. **Liberar o acesso das VMs (Redes Autorizadas):**
   - Vá no menu **Conexões** > aba **Rede**.
   - Em **Redes autorizadas**, clique em **Adicionar rede** e insira os IPs externos:
     - Nome: `vm-client` | Rede: `<IP_EXTERNO_VM_CLIENT>/32`
     - Nome: `vm-server` | Rede: `<IP_EXTERNO_VM_SERVER>/32`
   - Clique em **Salvar**.

#### 2. Firewall da VPC (Liberar a Interface Web)
1. Vá em **Rede VPC** > **Regras de Firewall** > **Criar regra de firewall**:
   - **Nome:** `allow-pix-gateway`
   - **Destino:** Todas as instâncias na rede
   - **Intervalos de IPv4 de origem:** `0.0.0.0/0`
   - **Protocolos e portas:** Marque `tcp` e digite `50051`.
2. Clique em **Criar**.

*(As portas internas gRPC `50052` e `50053` comunicam-se pelo IP interno da VPC e já são liberadas nativamente pela regra padrão `default-allow-internal` do GCP)*.

---

### Passo 2: Subir o Backend na `VM-client` (Nó gRPC)

Conecte via SSH na máquina **`VM-client`**:

```bash
cd ~/Trabalho-SD
git pull origin main
```

Você pode executar o script de 3 formas:

- **Modo Interativo (Recomendado):**
  ```bash
  ./scripts/run_vm_client.sh
  ```
  *(O script perguntará o IP do Cloud SQL e a senha caso não tenham sido passados)*.

- **Ou passando as variáveis diretamente:**
  ```bash
  DB_HOST="<IP_PUBLICO_CLOUD_SQL>" DB_PASSWORD="<SENHA_DO_BANCO>" ./scripts/run_vm_client.sh
  ```

- **Ou via arquivo `.env`:**
  ```bash
  cp .env.example .env
  # Edite os valores no .env e execute:
  ./scripts/run_vm_client.sh
  ```

**O que o script faz automaticamente:**
- Instala `python3-venv`, `python3-pip` e `tmux` (se necessário).
- Cria/ativa o ambiente virtual e instala as dependências.
- Testa a conectividade TCP na porta `5432` do Cloud SQL.
- Libera portas ocupadas e inicia `AccountService` (:50052) e `PixService` (:50053) em segundo plano no `tmux` (`sd_backend`).

> **Comandos úteis na VM-client:**
> - Ver logs ao vivo: `tmux attach -t sd_backend`
>   *(Verifique a confirmação: `[DATABASE] Conectado ao PostgreSQL com sucesso`)*
> - Alternar abas no tmux: `Ctrl + B`, depois `N`
> - Sair do tmux sem fechar os serviços: `Ctrl + B`, depois `D`

---

### Passo 3: Subir o API Gateway na `VM-Server` (Borda e Frontend)

Conecte via SSH na máquina **`VM-Server`**:

```bash
cd ~/Trabalho-SD
git pull origin main
```

Execute o script:

- **Modo Interativo:**
  ```bash
  ./scripts/run_vm_server.sh
  ```
  *(O script solicitará o IP Interno da `VM-client`)*.

- **Ou informando o IP interno diretamente:**
  ```bash
  BACKEND_HOST="<IP_INTERNO_VM_CLIENT>" ./scripts/run_vm_server.sh
  ```

**O que o script faz automaticamente:**
- Configura o ambiente Python e dependências.
- Configura a rota interna para o backend via VPC.
- Inicia o Flask REST na porta `50051` em segundo plano no `tmux` (`sd_gateway`).
- Detecta o IP público e exibe o link pronto para acesso no navegador.

> **Comandos úteis na VM-Server:**
> - Ver logs ao vivo do Gateway: `tmux attach -t sd_gateway`
> - Sair do tmux sem parar o Gateway: `Ctrl + B`, depois `D`

---

## Como Usar

### Interface Web (Navegador)
Com os serviços iniciados, acesse pelo navegador de qualquer dispositivo:
- **No GCP:** `http://<IP_EXTERNO_VM_SERVER>:50051/`
- **Localmente:** `http://localhost:50051/`

**Funcionalidades:**
- **Autenticação JWT Automática:** O frontend efetua login ao selecionar a conta e injeta `Authorization: Bearer <token>` em todas as requisições.
- **Transferência Real Pix:** O envio debita o remetente, credita o destinatário no PostgreSQL e retorna status **201 Created**.
- **Histórico Persistido:** Exibe as transações reais gravadas na tabela `transacoes` do banco de dados.

### Cliente de Linha de Comando (CLI)

```bash
source .venv/bin/activate
# Alice transfere R$ 50 para Bob
python client/client.py bob@pix.local 50.00
```

Para transferir de outra conta:
```bash
PIX_ORIGEM="bob@pix.local" python client/client.py alice@pix.local 25.00
```

---

## Testes Automatizados

Para executar a suíte de testes de integração ponta a ponta (validando 401 Unauthorized, 400 Bad Request, 201 Created, gRPC e persistência real no PostgreSQL):

```bash
source .venv/bin/activate
pytest -v tests/test_flow.py
```
