import os
import sys

# Garante que os stubs gerados no diretorio local possam ser importados
sys.path.insert(0, os.path.dirname(__file__))

import grpc
import pix_pb2
import pix_pb2_grpc


def run():
    server_host = os.getenv("SERVER_HOST", "localhost")
    endereco = f"{server_host}:50051"

    chave = sys.argv[1] if len(sys.argv) > 1 else "alice@pix.local"

    print(f"[*] Conectando ao Servidor gRPC em {endereco}...")
    with grpc.insecure_channel(endereco) as channel:
        stub = pix_pb2_grpc.PixServiceStub(channel)

        print(f"[*] Solicitando consulta para chave: '{chave}'")
        request = pix_pb2.SaldoRequest(chave_pix=chave)
        response = stub.ConsultarSaldo(request)

        print("\n--- Resposta gRPC Recebida ---")
        if response.sucesso:
            print(f"Titular : {response.titular}")
            print(f"Saldo   : R$ {response.saldo:.2f}")
            print(f"Mensagem: {response.mensagem}")
        else:
            print(f"Erro    : {response.mensagem}")


if __name__ == "__main__":
    run()