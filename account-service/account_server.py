from concurrent import futures
import os
import sys

# Inclusão dos diretórios no PYTHONPATH
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
GRPC_DIR = os.path.join(ROOT_DIR, "grpc-generated")
if GRPC_DIR not in sys.path:
    sys.path.insert(0, GRPC_DIR)

import grpc
import pix_pb2
import pix_pb2_grpc
from database.db import db


class AccountServicer(pix_pb2_grpc.AccountServiceServicer):

    def ConsultarConta(self, request, context):
        chave = request.chave_pix
        print(f"[ACCOUNT-SERVICE] Consulta de saldo para: '{chave}'")

        conta = db.query_one("SELECT titular, saldo FROM contas WHERE chave_pix = %s;", (chave,))
        if conta:
            return pix_pb2.SaldoResponse(
                sucesso=True,
                titular=conta["titular"],
                saldo=float(conta["saldo"]),
                mensagem="Conta localizada com sucesso."
            )

        return pix_pb2.SaldoResponse(
            sucesso=False,
            titular="",
            saldo=0.0,
            mensagem="Chave Pix não encontrada."
        )

    def Autenticar(self, request, context):
        chave = request.chave_pix
        senha = request.senha
        print(f"[ACCOUNT-SERVICE] Tentativa de login para: '{chave}'")

        conta = db.query_one("SELECT titular, senha FROM contas WHERE chave_pix = %s;", (chave,))
        if conta and conta["senha"] == senha:
            return pix_pb2.AuthResponse(
                sucesso=True,
                titular=conta["titular"],
                mensagem="Autenticação realizada com sucesso."
            )

        return pix_pb2.AuthResponse(
            sucesso=False,
            titular="",
            mensagem="Credenciais inválidas para a chave informada."
        )

    def DebitarConta(self, request, context):
        chave = request.chave_pix
        valor = float(request.valor)
        print(f"[ACCOUNT-SERVICE] Débito solicitado: '{chave}' - R$ {valor:.2f}")

        conta = db.query_one("SELECT saldo FROM contas WHERE chave_pix = %s;", (chave,))
        if not conta:
            return pix_pb2.MovimentacaoResponse(
                sucesso=False,
                saldo_atual=0.0,
                mensagem="Conta de origem não encontrada."
            )

        saldo_atual = float(conta["saldo"])
        if saldo_atual < valor:
            return pix_pb2.MovimentacaoResponse(
                sucesso=False,
                saldo_atual=saldo_atual,
                mensagem="Saldo insuficiente para a operação."
            )

        linhas_afetadas = db.execute(
            "UPDATE contas SET saldo = saldo - %s WHERE chave_pix = %s AND saldo >= %s;",
            (valor, chave, valor)
        )

        if linhas_afetadas > 0:
            novo_saldo = float(db.query_one("SELECT saldo FROM contas WHERE chave_pix = %s;", (chave,))["saldo"])
            return pix_pb2.MovimentacaoResponse(
                sucesso=True,
                saldo_atual=novo_saldo,
                mensagem="Débito efetuado com sucesso."
            )

        return pix_pb2.MovimentacaoResponse(
            sucesso=False,
            saldo_atual=saldo_atual,
            mensagem="Erro ao debitar valor da conta."
        )

    def CreditarConta(self, request, context):
        chave = request.chave_pix
        valor = float(request.valor)
        print(f"[ACCOUNT-SERVICE] Crédito solicitado: '{chave}' + R$ {valor:.2f}")

        conta = db.query_one("SELECT saldo FROM contas WHERE chave_pix = %s;", (chave,))
        if not conta:
            return pix_pb2.MovimentacaoResponse(
                sucesso=False,
                saldo_atual=0.0,
                mensagem="Conta de destino não encontrada."
            )

        db.execute(
            "UPDATE contas SET saldo = saldo + %s WHERE chave_pix = %s;",
            (valor, chave)
        )

        novo_saldo = float(db.query_one("SELECT saldo FROM contas WHERE chave_pix = %s;", (chave,))["saldo"])
        return pix_pb2.MovimentacaoResponse(
            sucesso=True,
            saldo_atual=novo_saldo,
            mensagem="Crédito efetuado com sucesso."
        )


def serve():
    porta = int(os.getenv("ACCOUNT_SERVICE_PORT", "50052"))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    pix_pb2_grpc.add_AccountServiceServicer_to_server(AccountServicer(), server)
    bound_port = server.add_insecure_port(f"0.0.0.0:{porta}")
    if bound_port == 0:
        raise RuntimeError(
            f"\n[ERRO CRÍTICO] Falha ao iniciar AccountService na porta {porta}!\n"
            f"A porta {porta} já pode estar sendo utilizada por outro processo ou bloqueada.\n"
            f"Execute: 'sudo lsof -i :{porta}' ou 'fuser -k {porta}/tcp' para liberar."
        )

    print("=" * 65)
    print(f"[*] [Microsserviço 1] AccountService ATIVO via gRPC na porta {bound_port}")
    print(f"[*] Escutando em: 0.0.0.0:{bound_port} (aceita conexões locais e remotas)")
    print(f"[*] Driver de Banco: {db.driver.upper()} (Host: {os.getenv('DB_HOST', 'localhost')})")
    print("=" * 65)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
