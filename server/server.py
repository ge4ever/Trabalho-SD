from concurrent import futures
import os
import sys

# Garante que os stubs gerados no diretorio local possam ser importados
sys.path.insert(0, os.path.dirname(__file__))

import grpc
import pix_pb2
import pix_pb2_grpc


class PixServicer(pix_pb2_grpc.PixServiceServicer):

    def ConsultarSaldo(self, request, context):
        chave = request.chave_pix

        print(f"[LOG] Consulta recebida para a chave: '{chave}'")

        # Conecta ao microservico de contas
        with grpc.insecure_channel("localhost:50052") as channel:

            account_stub = pix_pb2_grpc.AccountServiceStub(channel)

            # Encaminha a requisicao para o microservico
            response = account_stub.ConsultarConta(request)

        # Devolve ao cliente a resposta recebida
        return response


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
