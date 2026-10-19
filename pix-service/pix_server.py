from concurrent import futures
import datetime
import os
import sys
import uuid

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

def resolve_account_host():
    raw_val = os.getenv("ACCOUNT_SERVICE_HOST", "localhost:50052").strip()
    raw_val = raw_val.replace("http://", "").replace("https://", "").strip()
    if not raw_val:
        raw_val = "localhost:50052"
    if ":" not in raw_val:
        raw_val = f"{raw_val}:50052"
    return raw_val


ACCOUNT_SERVICE_HOST = resolve_account_host()


class PixServicer(pix_pb2_grpc.PixServiceServicer):

    def TransferirPix(self, request, context):
        origem = request.chave_origem
        destino = request.chave_destino
        valor = float(request.valor)
        descricao = request.descricao or "Transferência Pix"
        now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        print(f"[PIX-SERVICE] Transferência: '{origem}' -> '{destino}' no valor de R$ {valor:.2f}")

        if origem == destino:
            return pix_pb2.TransferenciaResponse(
                sucesso=False,
                transacao_id="",
                titular_origem="",
                titular_destino="",
                valor=valor,
                saldo_remanescente=0.0,
                mensagem="Chave de destino não pode ser igual à de origem.",
                data_hora=now_str
            )

        # Comunicação inter-microsserviços via gRPC com AccountService
        try:
            with grpc.insecure_channel(ACCOUNT_SERVICE_HOST) as channel:
                account_stub = pix_pb2_grpc.AccountServiceStub(channel)

                # 1. Consulta conta de origem
                resp_origem = account_stub.ConsultarConta(pix_pb2.SaldoRequest(chave_pix=origem))
                if not resp_origem.sucesso:
                    return pix_pb2.TransferenciaResponse(
                        sucesso=False,
                        mensagem="Conta de origem não encontrada.",
                        data_hora=now_str
                    )

                # 2. Consulta conta de destino
                resp_destino = account_stub.ConsultarConta(pix_pb2.SaldoRequest(chave_pix=destino))
                if not resp_destino.sucesso:
                    return pix_pb2.TransferenciaResponse(
                        sucesso=False,
                        titular_origem=resp_origem.titular,
                        saldo_remanescente=resp_origem.saldo,
                        mensagem="Chave Pix de destino não encontrada.",
                        data_hora=now_str
                    )

                # 3. Verifica saldo
                if resp_origem.saldo < valor:
                    return pix_pb2.TransferenciaResponse(
                        sucesso=False,
                        titular_origem=resp_origem.titular,
                        titular_destino=resp_destino.titular,
                        valor=valor,
                        saldo_remanescente=resp_origem.saldo,
                        mensagem="Pix não autorizado: saldo insuficiente.",
                        data_hora=now_str
                    )

                # 4. Efetua Débito via gRPC
                resp_debito = account_stub.DebitarConta(
                    pix_pb2.MovimentacaoRequest(chave_pix=origem, valor=valor)
                )
                if not resp_debito.sucesso:
                    return pix_pb2.TransferenciaResponse(
                        sucesso=False,
                        titular_origem=resp_origem.titular,
                        saldo_remanescente=resp_origem.saldo,
                        mensagem=resp_debito.mensagem,
                        data_hora=now_str
                    )

                # 5. Efetua Crédito via gRPC
                resp_credito = account_stub.CreditarConta(
                    pix_pb2.MovimentacaoRequest(chave_pix=destino, valor=valor)
                )
                if not resp_credito.sucesso:
                    # Rollback do débito em caso improvável de falha
                    account_stub.CreditarConta(pix_pb2.MovimentacaoRequest(chave_pix=origem, valor=valor))
                    return pix_pb2.TransferenciaResponse(
                        sucesso=False,
                        mensagem="Falha ao creditar destinatário. Operação desfeita.",
                        data_hora=now_str
                    )

                # 6. Registra no banco de dados real
                transacao_id = str(uuid.uuid4())[:8].upper()
                now_dt = datetime.datetime.now()
                now_str = now_dt.strftime("%d/%m/%Y %H:%M:%S")

                db.execute(
                    """
                    INSERT INTO transacoes (id, chave_origem, titular_origem, chave_destino, titular_destino, valor, status, mensagem, data_hora)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        transacao_id,
                        origem,
                        resp_origem.titular,
                        destino,
                        resp_destino.titular,
                        valor,
                        "CONCLUIDO",
                        descricao,
                        now_dt
                    )
                )

                print(f"[PIX-SERVICE] Pix [{transacao_id}] concluído com sucesso!")
                return pix_pb2.TransferenciaResponse(
                    sucesso=True,
                    transacao_id=transacao_id,
                    titular_origem=resp_origem.titular,
                    titular_destino=resp_destino.titular,
                    valor=valor,
                    saldo_remanescente=resp_debito.saldo_atual,
                    mensagem="Transferência Pix realizada com sucesso.",
                    data_hora=now_str
                )

        except grpc.RpcError as e:
            print(f"[ERRO] Falha gRPC ao comunicar com AccountService: {e}")
            return pix_pb2.TransferenciaResponse(
                sucesso=False,
                mensagem="Erro de comunicação com o serviço de contas.",
                data_hora=now_str
            )

    def ListarHistorico(self, request, context):
        chave = request.chave_pix
        rows = db.query_all(
            """
            SELECT id, chave_origem, titular_origem, chave_destino, titular_destino, valor, status, mensagem, data_hora
            FROM transacoes
            WHERE chave_origem = %s OR chave_destino = %s
            ORDER BY data_hora DESC;
            """,
            (chave, chave)
        )

        itens = []
        for r in rows:
            itens.append(pix_pb2.TransacaoItem(
                id=str(r["id"]),
                chave_origem=r["chave_origem"],
                titular_origem=r["titular_origem"],
                chave_destino=r["chave_destino"],
                titular_destino=r["titular_destino"],
                valor=float(r["valor"]),
                status=r["status"],
                mensagem=r["mensagem"] or "",
                data_hora=str(r["data_hora"])
            ))

        return pix_pb2.HistoricoResponse(transacoes=itens)

    def VerificarPix(self, request, context):
        chave = request.chave_pix
        valor = float(request.valor)
        try:
            with grpc.insecure_channel(ACCOUNT_SERVICE_HOST) as channel:
                account_stub = pix_pb2_grpc.AccountServiceStub(channel)
                conta = account_stub.ConsultarConta(pix_pb2.SaldoRequest(chave_pix=chave))

                if not conta.sucesso:
                    return pix_pb2.PixResponse(
                        sucesso=False,
                        titular="",
                        saldo=0.0,
                        valor=valor,
                        mensagem="Pix não autorizado: chave Pix não encontrada."
                    )

                if conta.saldo >= valor:
                    return pix_pb2.PixResponse(
                        sucesso=True,
                        titular=conta.titular,
                        saldo=conta.saldo,
                        valor=valor,
                        mensagem="Pix autorizado."
                    )

                return pix_pb2.PixResponse(
                    sucesso=False,
                    titular=conta.titular,
                    saldo=conta.saldo,
                    valor=valor,
                    mensagem="Pix não autorizado: saldo insuficiente."
                )
        except grpc.RpcError as e:
            return pix_pb2.PixResponse(
                sucesso=False,
                titular="",
                saldo=0.0,
                valor=valor,
                mensagem=f"Erro de comunicação gRPC: {e}"
            )


def serve():
    porta = int(os.getenv("PIX_SERVICE_PORT", "50053"))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    pix_pb2_grpc.add_PixServiceServicer_to_server(PixServicer(), server)
    bound_port = server.add_insecure_port(f"0.0.0.0:{porta}")
    if bound_port == 0:
        raise RuntimeError(
            f"\n[ERRO CRÍTICO] Falha ao iniciar PixService na porta {porta}!\n"
            f"A porta {porta} já pode estar sendo utilizada por outro processo ou bloqueada.\n"
            f"Execute: 'sudo lsof -i :{porta}' ou 'fuser -k {porta}/tcp' para liberar."
        )

    print("=" * 65)
    print(f"[*] [Microsserviço 2] PixService ATIVO via gRPC na porta {bound_port}")
    print(f"[*] Escutando em: 0.0.0.0:{bound_port} (aceita conexões locais e remotas)")
    print(f"[*] AccountService configurado em: {ACCOUNT_SERVICE_HOST}")
    print(f"[*] Driver de Banco: {db.driver.upper()} (Host: {os.getenv('DB_HOST', 'localhost')})")
    print("=" * 65)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
