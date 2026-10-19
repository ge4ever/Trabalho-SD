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

## Como Executar no Google Cloud Platform (GCP)

A aplicação está configurada para operar de forma distribuída em **3 Máquinas Virtuais (Compute Engine)** integradas ao banco gerenciado **Google Cloud SQL (PostgreSQL)**, permitindo demonstrar com clareza o papel e os logs em tempo real de cada microsserviço:

> [!IMPORTANT]
> Ao criar as três VMs no Compute Engine (Ubuntu 22.04+ ou Debian 11+), crie todas na **mesma Região** (ex: `us-central1`) e na **mesma rede VPC** (`default`). Isso garante que a comunicação gRPC entre elas ocorra via **IP interno privado**, com altíssima velocidade, sem custos de tráfego e com segurança.

### Topologia de Nós (3 VMs + Cloud SQL)

| Máquina / Instância | Papel no Sistema | IP Interno (VPC) | IP Externo (Público) | Portas Ativas |
|---|---|---|---|---|
| **`vm1`** | API Gateway (Flask REST) + Frontend Web | `<IP_INTERNO_VM1>` | `<IP_EXTERNO_VM1>` | `50051` (Pública) |
| **`vm2`** | `AccountService` (gRPC) | `<IP_INTERNO_VM2>` | `<IP_EXTERNO_VM2>` | `50052` (VPC Interna) |
| **`vm3`** | `PixService` (gRPC) | `<IP_INTERNO_VM3>` | `<IP_EXTERNO_VM3>` | `50053` (VPC Interna) |
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
   - Em **Redes autorizadas**, clique em **Adicionar rede** e insira os IPs externos das máquinas:
     - Nome: `vm1` | Rede: `<IP_EXTERNO_VM1>/32`
     - Nome: `vm2` | Rede: `<IP_EXTERNO_VM2>/32`
     - Nome: `vm3` | Rede: `<IP_EXTERNO_VM3>/32`
   - Clique em **Salvar**.

#### 2. Firewall da VPC (Liberar a Interface Web)
1. Vá em **Rede VPC** > **Regras de Firewall** > **Criar regra de firewall**:
   - **Nome:** `allow-pix-gateway`
   - **Destino:** Todas as instâncias na rede
   - **Intervalos de IPv4 de origem:** `0.0.0.0/0`
   - **Protocolos e portas:** Marque `tcp` e digite `50051`.
2. Clique em **Criar**.

*(As portas internas gRPC `50052` e `50053` comunicam-se pelos IPs internos da VPC e já são liberadas nativamente pela regra padrão `default-allow-internal` do GCP)*.

---

### Passo 2: Subir o `AccountService` na `vm2`

Conecte via SSH na máquina **`vm2`**:

```bash
git clone https://github.com/ge4ever/Trabalho-SD.git
cd ~/Trabalho-SD
python3 -m venv --clear .venv
./scripts/run_vm2.sh
```
*(Ou execute passando parâmetros diretamente: `DB_HOST="<IP_CLOUD_SQL>" DB_PASSWORD="<SENHA>" ./scripts/run_vm2.sh`)*.

**O que o script faz automaticamente:**
- Configura o ambiente Python (`.venv` e dependências).
- Testa a conectividade TCP na porta `5432` do Cloud SQL.
- Inicia o `AccountService` na porta `50052` em segundo plano no `tmux` (`sd_account`).

> **Para ver os logs na `vm2`:** `tmux attach -t sd_account`  
> *(Para sair sem fechar: `Ctrl + B`, depois `D`)*

---

### Passo 3: Subir o `PixService` na `vm3`

Conecte via SSH na máquina **`vm3`**:

```bash
git clone https://github.com/ge4ever/Trabalho-SD.git
cd ~/Trabalho-SD
python3 -m venv --clear .venv
./scripts/run_vm3.sh
```
*(O script solicitará o IP do Cloud SQL e o IP Interno da `vm2`, ou passe diretamente: `DB_HOST="<IP_CLOUD_SQL>" ACCOUNT_SERVICE_HOST="<IP_INTERNO_VM2>" ./scripts/run_vm3.sh`)*.

**O que o script faz automaticamente:**
- Configura o ambiente Python.
- Testa a conectividade com o Cloud SQL e com a `vm2` (`AccountService:50052`).
- Inicia o `PixService` na porta `50053` em segundo plano no `tmux` (`sd_pix`).

> **Para ver os logs na `vm3`:** `tmux attach -t sd_pix`  
> *(Para sair sem fechar: `Ctrl + B`, depois `D`)*

---

### Passo 4: Subir o API Gateway e Frontend na `vm1`

Conecte via SSH na máquina **`vm1`**:

```bash
git clone https://github.com/ge4ever/Trabalho-SD.git
cd ~/Trabalho-SD
python3 -m venv --clear .venv
./scripts/run_vm1.sh
```
*(O script solicitará os IPs internos da `vm2` e da `vm3`, ou passe diretamente: `ACCOUNT_SERVICE_HOST="<IP_INTERNO_VM2>" PIX_SERVICE_HOST="<IP_INTERNO_VM3>" ./scripts/run_vm1.sh`)*.

**O que o script faz automaticamente:**
- Configura o ambiente Python e rotas para os dois microsserviços.
- Inicia o Flask REST na porta `50051` em segundo plano no `tmux` (`sd_gateway`).
- Detecta o IP público e exibe a URL pronta para acesso no navegador: `http://<IP_EXTERNO_VM1>:50051/`.

> **Para ver os logs na `vm1`:** `tmux attach -t sd_gateway`  
> *(Para sair sem fechar: `Ctrl + B`, depois `D`)*

---

### Demonstração dos Microsserviços para o Professor

Com as 3 VMs ativas, abra 3 janelas de terminal lado a lado conectadas via SSH:

1. **Janela 1 (`vm1` - `tmux attach -t sd_gateway`):**
   - Ao clicar no navegador ou no CLI, você verá a requisição HTTP REST chegando, a validação de JWT, a semântica de status codes (`401`, `400`, `201`) e o despacho binário gRPC.
2. **Janela 2 (`vm2` - `tmux attach -t sd_account`):**
   - Veja as consultas de saldo, a autenticação de credenciais e os débitos/créditos atômicos sendo solicitados pelo Gateway e pelo PixService.
3. **Janela 3 (`vm3` - `tmux attach -t sd_pix`):**
   - Ao executar uma transferência Pix, veja a orquestração transacional: a `vm3` faz chamadas remotas gRPC para a `vm2` (inter-microsserviços) e registra a transação final no Cloud SQL.

---

## Como Usar

### Interface Web (Navegador)
Com os serviços iniciados, acesse pelo navegador de qualquer dispositivo:
- **No GCP:** `http://<IP_EXTERNO_VM1>:50051/`
- **Localmente:** `http://localhost:50051/`

**Funcionalidades:**
- **Autenticação JWT Automática:** O frontend efetua login ao selecionar a conta e injeta `Authorization: Bearer <token>` em todas as requisições.
- **Transferência Real Pix:** O envio debita o remetente, credita o destinatário no PostgreSQL e retorna status **201 Created**.
- **Histórico Persistido:** Exibe as transações reais gravadas na tabela `transacoes` do banco de dados.

### Cliente de Linha de Comando (CLI)

```bash
source .venv/bin/activate
# Alice transfere R$ 50 para Bob (local ou definindo SERVER_HOST=<IP_EXTERNO_VM1>)
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
