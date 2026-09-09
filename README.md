# Trabalho 1 - Sistema de contas e verifivação de transações bancárias (estilo pix)

## Descrição do projeto
O projeto consiste em uma versão inicial e bem simplificada de transações bancárias inspiradas no Pix, utilizando o gRCP. O
sistema funciona em cima de dois microserviços básicos, o `PixService` que recebe uma requisição do cliente e é reponsável
por consultar o `AccountServie`, que fornece os dados da conta, a partir desse retorno o `PixService` avalia o saldo da conta e
verifica se a transação pode ser realizada. O cliente então recebe uma mensagem com as informações relacionadas a sua requisição.

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

Temos então, de forma geral duas comunicações usando gRPC com mensagens definidas por meio de Protocol Buffers, e essa comunicação
é estabelecida e configurada por meio de portas, liberando a conversa entre os serviços.

Componentes
