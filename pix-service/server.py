from concurrent import futures
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import grpc
import pix_pb2
import pix_pb2_grpc


class PixServicer(pix_pb2_grpc.PixServiceServicer):

    def ConsultarSaldo(self, request, context):
        chave = request.chave_pix

        print(f"[LOG] Consulta recebida para a chave: '{chave}'")

        # conecta ao microserviço de contas
        with grpc.insecure_channel("localhost:50052") as channel:

            account_stub = pix_pb2_grpc.AccountServiceStub(channel)

            # encaminha a requisição 
            response = account_stub.ConsultarConta(request)

        # devolve a resposta recebida
        return response

    def VerificarPix(self, request, context):
        chave = request.chave_pix

        valor = request.valor

        print(
            f"[LOG] Verificação de Pix para a chave "
            f"'{chave}' no valor de R$ {valor:.2f}"
        )

        # consulta os dados da conta
        with grpc.insecure_channel("localhost:50052") as channel:

            account_stub = pix_pb2_grpc.AccountServiceStub(channel)

            saldo_request = pix_pb2.SaldoRequest(
                chave_pix=chave
            )

            conta = account_stub.ConsultarConta(saldo_request)

        # se a conta não foi encontrada, rejeita o Pix
        if not conta.sucesso:
            return pix_pb2.PixResponse(
                sucesso=False,
                titular="",
                saldo=0.0,
                valor=valor,
                mensagem="Pix não autorizado: chave Pix não encontrada."
            )

        # o saldo precisa ser suficiente
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


def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=5)
    )

    pix_pb2_grpc.add_PixServiceServicer_to_server(
        PixServicer(),
        server
    )

    server.add_insecure_port("0.0.0.0:50051")

    print("[*] Servidor gRPC ativo na porta 50051...")

    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
