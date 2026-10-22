# Trabalho 2 - Sistema Distribuído de Contas e Transações Pix com exposição WEB e API Gateway

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
   - `AccountService` (gRPC na porta `50052`): Autenticar usuários, consultar contas e executar créditos e débitos.
   - `PixService` (gRPC na porta `50053`): Processamento transacional de transferências, histórico e verificação da existência de contas.
   - Comunicação backend baseada em gRPC com Protocol Buffers.
4. **Banco de Dados Real (Sem Mocks):**
   - Conectado a PostgreSQL operacional (Google Cloud SQL no GCP ou PostgreSQL local) com tabelas reais `contas` e `transacoes`.
   - Todas as consultas, alterações de saldo e transferências refletem de fato no banco (zero mocks ou listas na memória).
   - Suporte a fallback automático em SQLite (`database/banco_sd.db`) caso o PostgreSQL não esteja em execução.
5. **Validação no Backend:** Validação obrigatória de dados de negócio no Gateway com retorno explícito de `400 Bad Request` para erros e `201 Created` para transferências realizadas.
6. **Segurança (Autenticação JWT):** Middleware de segurança no API Gateway exigindo `Authorization: Bearer <token>`. Bloqueio imediato na borda com `401 Unauthorized` se token inválido ou ausente.
7. **Tradução e Delegação de Protocolo:** Recebe JSON, desserializa, autentica, valida e serializa em chamadas gRPC/Protobuf binárias para os microsserviços internos.

---

## Arquitetura do Sistema

```text
                        USUÁRIO
                           |
                           v
                +----------------------+
                |    FRONTEND WEB      |
                |    HTML/CSS/JS       |
                +----------------------+
                          |
                          | HTTP/JSON (REST) + JWT Bearer Token
                          v
                +----------------------+
                |     API GATEWAY      |
                |    Flask :50051      |
                |                      |
                | - Autenticação JWT   |
                | - Validação de dados |
                | - Tradução de dados  |
                +----------------------+
                  |                   |
       gRPC :50052|                   | gRPC :50053
                  v                   v
        +----------------+     +----------------+
        | AccountService |     |   PixService   |
        |                |     |                |
        | - Autenticação |     | - Transferir   |
        | - Consultar    |     | - Histórico    |
        | - Debitar      |     | - Verificar Pix|
        | - Creditar     |     |                |
        +----------------+     +----------------+
                 |                     |
                 +----------+----------+
                            | 
                            v
                   +---------------+
                   |    BANCO      |
                   |  PostgreSQL   |
                   | ou SQLite     |
                   +---------------+
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
> Ao criar as três VMs no Compute Engine (Ubuntu 22.04+ ou Debian 11+), crie todas na **mesma Região** (ex: `us-central1`) e na **mesma rede VPC** (`default`). Isso garante que a comunicação gRPC entre elas ocorra via **IP interno privado**, com altíssima velocidade, sem custos de tráfego e com segurança. Lembre também de configurar o Firewall das VMs para permitir tráfego HTTP e HTTPS. Por fim, não se esqueça de ao iniciar as VMs instalar o git e o pyhton.

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
   - No painel da sua instância Cloud SQL do PostgreSQL já criada, vá no menu **Bancos de dados** > clique em **Criar banco de dados**.
   - Nome do banco: `banco-sd`.
2. **Criar o usuário do banco:**
   - No menu lateral **Usuários** > clique em **Adicionar conta de usuário**.
   - Usuário: `sd_user` | Senha: `Sistemas#26` (ou a senha de sua preferência).
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
sudo apt install python3-venv
python3 -m venv --clear .venv
./scripts/run_vm2.sh
```
*(O script vai soliciar as informações sobre o banco de dados e usuário, por isso é importante lembrar de sua senha)*.

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
sudo apt install python3-venv
python3 -m venv --clear .venv
./scripts/run_vm3.sh
```
*(O script solicitará informações do Cloud SQL e o IP Interno da `vm2`)*.

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
sudo apt install python3-venv
python3 -m venv --clear .venv
./scripts/run_vm1.sh
```
*(O script solicitará os IPs internos da `vm2` e da `vm3`)*.

**O que o script faz automaticamente:**
- Configura o ambiente Python e rotas para os dois microsserviços.
- Inicia o Flask REST na porta `50051` em segundo plano no `tmux` (`sd_gateway`).
- Detecta o IP público e exibe a URL pronta para acesso no navegador: `http://<IP_EXTERNO_VM1>:50051/`.

> **Para ver os logs na `vm1`:** `tmux attach -t sd_gateway`  
> *(Para sair sem fechar: `Ctrl + B`, depois `D`)*

---
### Como usar a interface web
- Para entender como usar a interface web e seus usuários basta ir para a seção **Como usar** logo abaixo do tutorial para executar localmente.

---

## Como Executar Localmente (Desenvolvimento)

Caso prefira executar todo o ecossistema na sua máquina local sem depender de instâncias na nuvem, você pode optar pela execução rápida via script automatizado ou pelo modo passo a passo em 3 terminais separados.

> [!TIP]
> **Banco de Dados Local:** O sistema utiliza automaticamente o banco SQLite relacional persistente em `database/banco_sd.db` com as contas de teste (`alice`, `bob`, `admin`) e histórico de transações pré-carregados. Não é necessário instalar ou rodar nenhum container ou serviço de banco externo. Caso você possua um PostgreSQL local rodando na porta `5432`, o sistema conectará a ele automaticamente se desejar.

### Pré-requisitos
- Python 3.10+ (ou compatível com seu ambiente)
- Git e `pip`
- (Opcional) `tmux` para gerenciar os serviços em segundo plano

---

### Opção 1: Execução Rápida via Script (Recomendado)

O projeto inclui o script [`scripts/run_local.sh`](scripts/run_local.sh) que configura o ambiente virtual, instala as dependências, compila os arquivos do Protocol Buffers e inicia os 3 serviços automaticamente:

```bash
git clone https://github.com/ge4ever/Trabalho-SD.git
cd Trabalho-SD
./scripts/run_local.sh
```

**Comandos úteis:**
- **Acompanhar os logs em tempo real (via tmux):**
  ```bash
  tmux attach -t sd_local
  ```
  *(Dica: use `Ctrl + B`, depois `0` para o AccountService, `1` para o PixService e `2` para o API Gateway. Para sair sem encerrar os serviços: `Ctrl + B`, depois `D`)*.
- **Encerrar todos os serviços locais:**
  ```bash
  ./scripts/run_local.sh stop
  ```

---

### Opção 2: Execução Passo a Passo (3 Terminais)

Se preferir rodar e acompanhar cada microsserviço individualmente em janelas de terminal abertas:

#### 1. Preparar o Ambiente e Dependências (Terminal 1)
```bash
git clone https://github.com/ge4ever/Trabalho-SD.git
cd Trabalho-SD
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2. Compilar os Protocol Buffers (gRPC)
*(Os arquivos já vêm pré-compilados em `grpc-generated/`, mas você pode recompilar a qualquer momento)*:
```bash
python -m grpc_tools.protoc -I proto --python_out=grpc-generated --grpc_python_out=grpc-generated proto/pix.proto
```

#### 3. Iniciar o AccountService (Terminal 1 - Porta 50052)
```bash
source .venv/bin/activate
LOCAL=1 python account-service/account_server.py
```

#### 4. Iniciar o PixService (Terminal 2 - Porta 50053)
Abra um segundo terminal no diretório do projeto:
```bash
cd ~/Trabalho-SD
source .venv/bin/activate
LOCAL=1 python pix-service/pix_server.py
```

#### 5. Iniciar o API Gateway & Frontend (Terminal 3 - Porta 50051)
Abra um terceiro terminal no diretório do projeto:
```bash
cd ~/Trabalho-SD
source .venv/bin/activate
LOCAL=1 python gateway/server.py
```

---

## Como Usar

### Interface Web (Navegador)
Com os serviços iniciados, acesse pelo navegador de qualquer dispositivo:
- **No GCP:** `http://<IP_EXTERNO_VM1>:50051/`
- **Localmente:** `http://localhost:50051/`

**Funcionalidades:**
- **Autenticação JWT e Tela de Login:** Acesso seguro com chave Pix e senha. Demonstração em tempo real de `401 Unauthorized` na tela caso as credenciais sejam incorretas.
- **Perfis de Usuário:**
  - *Usuário Comum:* Acesso restrito à própria conta (`alice@pix.local` ou `bob@pix.local` com senha `123456`).
  - *Administrador Geral:* Permissão de supervisão para auditar e alternar entre todas as contas (`admin@pix.local` com senha `admin123`).
- **Transferência Real Pix:** O envio debita o remetente, credita o destinatário no PostgreSQL e retorna status **201 Created**.
- **Transferência com Erro** Existe a possibilidade de o usuário tentar debitar um saldo em sua própria conta, ou tentar realizar uma transação de um valor maior que a quantidade que ele possui em saldo. Em ambos os casos o sistema identifica esses erros e retorna um **400 Bad Request**.
- **Histórico Persistido:** Exibe as transações reais gravadas na tabela `transacoes` do banco de dados relacional.
- **Logout Seguro:** Encerramento de sessão no canto superior direito para alternar de usuário.

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
