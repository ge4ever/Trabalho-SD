# Trabalho 1 - Sistema de contas e verificação de transações bancárias (estilo pix)

#### Participantes
Geovana Ribeiro Araújo Espinosa - 202405104

Dennis Lucas Gonçalves - 202400839

Vitor Vittorete Serafim de Pina - 202405128

## Descrição do projeto
O projeto consiste em uma versão inicial e bem simplificada de transações bancárias inspiradas no Pix, utilizando o gRPC. O
sistema funciona em cima de dois microserviços básicos, o `PixService` que recebe uma requisição do cliente e é responsável
por consultar o `AccountService`, que fornece os dados da conta, a partir desse retorno o `PixService` avalia o saldo da conta e
verifica se a transação pode ser realizada. O cliente então recebe uma mensagem com as informações relacionadas a sua requisição.

<img width="450" height="296" alt="WhatsApp Image 2026-09-09 at 22 25 08" src="https://github.com/user-attachments/assets/844b0268-7dd0-409e-8da9-0295884e574a" />


## Arquitetura do projeto

```text
     Cliente
        |
        | gRPC :50051
        v
    PixService
        |
        | gRPC :50052
        v
   AccountService
        |
        v
   CONTAS_MOCK
```

Temos então, de forma geral duas comunicações usando gRPC com mensagens definidas por meio de Protocol Buffers, cada serviço utiliza uma porta específica para estabelecer sua comunicação.

Componentes

| Componente        | Responsabilidade                                           |
|-------------------|------------------------------------------------------------|
| `proto`           | Define o contrato gRPC                                     |
| `pix-service`     | Recebe as requisições, verifica os saldos                  |
| `account-service` | Consulta e fornece os dados das contas                     |
| `client`          | Envia as requisições                                       |

Os dados das contas que são utilizados nessa fase inicial do sistema são todos fixos para facilitar as consultas, ou seja, não há integração com banco de dados.

Portas


| Componente        | Porta    | Responsabilidade                                |
|-------------------|----------|-------------------------------------------------|
| `pix-service`     | 50051    | Comunicação com o cliente                       |
| `account-service`  | 50052    | Comunicação interna                             |

O AccountService é acessado pelo PixService através de localhost:50052.

## Como compilar o projeto

Esse trabalho pode rodar 100% localmente se você preferir, nesse caso basta seguir as instruções abaixo em terminais da sua
própria máquina, basta colocar as requisições do cliente sem o SERVER_HOST que aponta para o IP externo. 

É muito importante que a porta 50051 esteja configurada e liberada na VM.

### SSH 1 da VM para o AccountService

Abra um terminal em uma máquina virtual, nesse caso, pelo SSH de uma VM do GCP. É necessário que a máquina tenha o Python e o Git instalados.

Decidimos rodar o trabalho usando o .venv para criar um ambiente virtual isolado.

```bash
git clone https://github.com/ge4ever/Trabalho-SD.git
cd Trabalho-SD
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Gere os arquivos gRPC

```bash
python -m grpc_tools.protoc -I proto --python_out=grpc-generated --grpc_python_out=grpc-generated proto/pix.proto
```

Inicie o serviço

```bash
python account-service/account_server.py
```

### SSH 2 da VM para o PixService

Abra um outro terminal SSH na mesma VM (é importante que seja a mesma para que não haja problema com portas, mas se você quiser abrir em duas diferentes basta configurar a porta dessa segunda e clonar e recompilar o projeto).

```bash
cd ~/Trabalho-SD
source .venv/bin/activate
```

Inicie o serviço


```bash
python pix-service/server.py
```

### Cliente local

Abra um terminal localmente em sua máquina, ela também deve ter o python e git instalados.

```bash
git clone https://github.com/ge4ever/Trabalho-SD.git
cd Trabalho-SD
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Gere os arquivos

```bash
python -m grpc_tools.protoc -I proto --python_out=grpc-generated --grpc_python_out=grpc-generated proto/pix.proto
```

Execute a consulta (essa consulta é apenas uma base geral, abaixo temos comandos funcionais)


```bash
SERVER_HOST=IP_EXTERNO_DA_VM python client/client.py
```
Repare que este último comando contém `IP_EXTERNO_DA_VM`, nessa parte é necessário que você a substitua pelo IP externo que aparece na instância de sua VM.

A seguir separamos umas sugestões de consulta que abrangem bem o escopo do projeto:

**Verificação de um pix**
```bash
SERVER_HOST=IP_EXTERNO_DA_VM python client/client.py alice@pix.local 100
```

_Saída esperada_
```bash
[*] Conectando ao Servidor gRPC em IP_EXTERNO_DA_VM:50051...
[*] Verificando Pix para 'alice@pix.local' no valor de R$ 100.00

--- Resultado da Verificação Pix ---
Titular : Alice Silva Saldo : R$ 1250.75
Valor : R$ 100.00
Resultado: Pix autorizado.
```

**Saldo insuficiente**
```bash
SERVER_HOST=IP_EXTERNO_DA_VM python client/client.py alice@pix.local 1500
```

_Saída esperada_
```bash
[*] Conectando ao Servidor gRPC em IP_EXTERNO_DA_VM:50051...
[*] Verificando Pix para 'alice@pix.local' no valor de R$ 1500.00

--- Resultado da Verificação Pix ---
Titular : Alice Silva Saldo : R$ 1250.75
Valor : R$ 1500.00
Resultado: Pix não autorizado: saldo insuficiente.
```

***Conta não encontrada***
```bash
SERVER_HOST=IP_EXTERNO_DA_VM python client/client.py qualquer@pix.local 100
```

_Saída esperada_
```bash
[*] Conectando ao Servidor gRPC em IP_EXTERNO_DA_VM:50051...
[*] Verificando Pix para 'qualquer@pix.local' no valor de R$ 100.00

--- Resultado da Verificação Pix ---
Titular : Saldo : R$ 0.00
Valor : R$ 100.00
Resultado: Pix não autorizado: chave Pix não encontrada.
```


## Observação
Pode acontecer de haver problemas com timeout, isso normalmente ocorre quando o cliente não consegue alcançar a porta do servidor, principalmente em redes Wi-Fi públicas que possuem configurações de portas específicas, se for caso, basta mudar para uma rede diferente, como uma conexão roteada pelo seu dispositivo móvel.
