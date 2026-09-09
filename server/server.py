from concurrent import futures
import os
import sys

# Garante que os stubs gerados no diretorio local possam ser importados
sys.path.insert(0, os.path.dirname(__file__))

import grpc
import pix_pb2
import pix_pb2_grpc

CONTAS_MOCK = {
    "alice@pix.local": {"titular": "Alice Silva", "saldo": 1250.75},
    "bob@pix.local": {"titular": "Bob Santos", "saldo": 340.20},
}


class PixServicer(pix_pb2_grpc.PixServiceServicer):
    def ConsultarSaldo(self, request, context):
        chave = request.chave_pix
        print(f"[LOG] Consulta recebida para a chave: '{chave}'")

        if chave in CONTAS_MOCK:
            conta = CONTAS_MOCK[chave]
            return pix_pb2.SaldoResponse(
                sucesso=True,
                titular=conta["titular"],
                saldo=conta["saldo"],
                mensagem="Conta localizada com sucesso.",
            )

        return pix_pb2.SaldoResponse(
            sucesso=False,
            titular="",
            saldo=0.0,
            mensagem="Chave Pix não encontrada.",
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    pix_pb2_grpc.add_PixServiceServicer_to_server(PixServicer(), server)
    server.add_insecure_port("0.0.0.0:50051")
    print("[*] Servidor gRPC ativo na porta 50051...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()